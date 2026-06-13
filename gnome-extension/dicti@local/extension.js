/* dicti dictation, GNOME Shell panel indicator.
 *
 * One icon that mirrors the daemon's state file ($XDG_RUNTIME_DIR/dictation.state).
 * Left-click toggles dictation; right-click opens a Toggle / Cancel menu. No
 * AppIndicator needed, so no other apps' tray icons are pulled in.
 *
 * Placed in the CENTRE box (by the clock): GNOME inserts its privacy
 * microphone indicator into the RIGHT box while recording, which shoves the
 * right-hand icons around. Living in the centre keeps our icon from jumping.
 */

import GObject from 'gi://GObject';
import St from 'gi://St';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Clutter from 'gi://Clutter';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as Animation from 'resource:///org/gnome/shell/ui/animation.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

// Where to live in the top bar. Centre avoids the right-box reflow when GNOME's
// privacy mic indicator appears. Tweak if the placement looks off.
const PANEL_BOX = 'center';
const PANEL_INDEX = 1;

const ICONS = {
    IDLE: 'audio-input-microphone-symbolic',
    LISTENING: 'media-record-symbolic',
};

const DictiIndicator = GObject.registerClass(
class DictiIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, 'dicti', false);

        const box = new St.BoxLayout({style_class: 'panel-status-indicators-box'});
        this._icon = new St.Icon({
            icon_name: ICONS.IDLE,
            style_class: 'system-status-icon',
        });
        // A real spinning wheel for the transcribing state (clearer than dots).
        this._spinner = new Animation.Spinner(16, {animate: true, hideOnStop: true});
        box.add_child(this._icon);
        box.add_child(this._spinner);
        this.add_child(box);
        this._spinner.stop();  // hidden until processing

        const toggleItem = new PopupMenu.PopupMenuItem('Toggle dictation');
        toggleItem.connect('activate', () => this._send('TOGGLE'));
        this.menu.addMenuItem(toggleItem);

        const cancelItem = new PopupMenu.PopupMenuItem('Cancel');
        cancelItem.connect('activate', () => this._send('CANCEL'));
        this.menu.addMenuItem(cancelItem);

        // Left-click toggles directly; right-click falls through to the menu.
        this.connect('button-press-event', (_actor, event) => {
            if (event.get_button() === Clutter.BUTTON_PRIMARY) {
                this._send('TOGGLE');
                return Clutter.EVENT_STOP;
            }
            return Clutter.EVENT_PROPAGATE;
        });

        this._statePath = GLib.build_filenamev(
            [GLib.get_user_runtime_dir(), 'dictation.state']);
        this._file = Gio.File.new_for_path(this._statePath);
        try {
            this._monitor = this._file.monitor(Gio.FileMonitorFlags.NONE, null);
            this._monitorId = this._monitor.connect('changed', () => this._update());
        } catch (e) {
            logError(e, 'dicti: could not watch state file');
        }
        // Poll as a safety net (tmpfs inotify can be flaky).
        this._pollId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 2, () => {
            this._update();
            return GLib.SOURCE_CONTINUE;
        });

        this._update();
    }

    _readState() {
        try {
            const [ok, contents] = GLib.file_get_contents(this._statePath);
            if (ok)
                return (new TextDecoder().decode(contents)).trim() || 'IDLE';
        } catch (e) {
            // file may not exist yet
        }
        return 'IDLE';
    }

    _update() {
        const state = this._readState();
        if (state === 'PROCESSING') {
            this._icon.hide();
            this._spinner.show();
            this._spinner.play();
            return;
        }
        this._spinner.stop();
        this._icon.show();
        this._icon.icon_name = ICONS[state] ?? ICONS.IDLE;
        if (state === 'LISTENING')
            this._icon.add_style_class_name('dicti-listening');
        else
            this._icon.remove_style_class_name('dicti-listening');
    }

    _send(cmd) {
        try {
            Gio.Subprocess.new(
                [GLib.build_filenamev([GLib.get_home_dir(), '.local', 'bin', 'dictate-toggle']), cmd],
                Gio.SubprocessFlags.NONE);
        } catch (e) {
            logError(e, 'dicti: failed to run dictate-toggle');
        }
    }

    destroy() {
        if (this._pollId) {
            GLib.source_remove(this._pollId);
            this._pollId = null;
        }
        if (this._monitor) {
            if (this._monitorId)
                this._monitor.disconnect(this._monitorId);
            this._monitor.cancel();
            this._monitor = null;
        }
        super.destroy();
    }
});

export default class DictiExtension extends Extension {
    enable() {
        this._indicator = new DictiIndicator();
        Main.panel.addToStatusArea('dicti', this._indicator, PANEL_INDEX, PANEL_BOX);
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
