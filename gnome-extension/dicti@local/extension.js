/* dicti dictation, GNOME Shell panel indicator.
 *
 * One custom-drawn icon that mirrors the daemon's state file
 * ($XDG_RUNTIME_DIR/dictation.state). The icon is a set of five bars rendered
 * with Cairo, animated per state (see specs/0001 and design/icon-preview-v3):
 *   IDLE       static "trapezoid" mic silhouette, deep green
 *   LISTENING  organic equalizer bounce (random walk), pink
 *   PROCESSING left->right "fill" progress, deep green
 *
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
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

// Where to live in the top bar. Centre avoids the right-box reflow when GNOME's
// privacy mic indicator appears. Tweak if the placement looks off.
const PANEL_BOX = 'center';
const PANEL_INDEX = 1;

// Brand colors (deep green + pink accent), RGB 0..1.
const GREEN = [0x3c / 255, 0x9a / 255, 0x5e / 255];
const PINK = [0xe8 / 255, 0x5b / 255, 0xa6 / 255];

const N_BARS = 5;
const AREA_W = 22;          // logical px; St scales for HiDPI
const AREA_H = 16;
const FPS_MS = 33;          // ~30fps while animating
const FILL_PERIOD = 1700;   // ms, one processing fill cycle
const FILL_STAGGER = 160;   // ms, per-bar delay in the fill

// IDLE "trapezoid" mic: three tall middle bars + short shoulders (0..1).
const IDLE_HEIGHTS = [0.5, 1.0, 1.0, 1.0, 0.5];

function clamp(v, lo, hi) {
    return v < lo ? lo : v > hi ? hi : v;
}

// One bar's height (0..1) in the processing "fill" cycle, given global ms.
function fillHeight(nowMs, i) {
    const lp = (((nowMs - i * FILL_STAGGER) % FILL_PERIOD) + FILL_PERIOD)
        % FILL_PERIOD / FILL_PERIOD;        // local progress 0..1
    if (lp < 0.28)
        return 0.18 + (1.0 - 0.18) * (lp / 0.28);
    if (lp < 0.82)
        return 1.0;
    return 1.0 - (1.0 - 0.18) * ((lp - 0.82) / 0.18);
}

const DictiIndicator = GObject.registerClass(
class DictiIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, 'dicti', false);

        this._state = 'IDLE';
        this._timerId = 0;
        // Listening equalizer state: smoothed current heights + random targets.
        this._eqCur = new Array(N_BARS).fill(0.3);
        this._eqTgt = new Array(N_BARS).fill(0.3);
        this._eqNext = new Array(N_BARS).fill(0);

        this._area = new St.DrawingArea({
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'dicti-bars',
        });
        this._area.set_size(AREA_W, AREA_H);
        this._area.connect('repaint', a => this._repaint(a));
        this.add_child(this._area);

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
        this._area.queue_repaint();   // draw the idle mark once on startup
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
        if (state === this._state)
            return;                            // no transition: nothing to redraw
        this._state = state;
        if (state === 'IDLE') {
            this._stopAnim();
            this._area.queue_repaint();
        } else {
            if (state === 'LISTENING') {
                // reset equalizer so it doesn't jump from a stale pose
                const now = GLib.get_monotonic_time() / 1000;
                for (let i = 0; i < N_BARS; i++) {
                    this._eqCur[i] = 0.3;
                    this._eqNext[i] = now;
                }
            }
            this._startAnim();
        }
    }

    _startAnim() {
        if (this._timerId)
            return;
        this._timerId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, FPS_MS, () => {
            if (this._state === 'LISTENING')
                this._tickEq();
            this._area.queue_repaint();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _stopAnim() {
        if (this._timerId) {
            GLib.source_remove(this._timerId);
            this._timerId = 0;
        }
    }

    // Organic equalizer: re-pick a random target per bar on its own cadence,
    // ease the current height toward it. Looks alive, not strobing.
    _tickEq() {
        const now = GLib.get_monotonic_time() / 1000;   // ms
        for (let i = 0; i < N_BARS; i++) {
            if (now >= this._eqNext[i]) {
                // bias toward mid heights (Math.random squared) so it breathes
                this._eqTgt[i] = 0.28 + Math.random() * Math.random() * 0.72;
                this._eqNext[i] = now + 120 + Math.random() * 160;
            }
            this._eqCur[i] += (this._eqTgt[i] - this._eqCur[i]) * 0.25;
        }
    }

    _heights() {
        if (this._state === 'LISTENING')
            return this._eqCur;
        if (this._state === 'PROCESSING') {
            const now = GLib.get_monotonic_time() / 1000;
            return Array.from({length: N_BARS}, (_, i) => fillHeight(now, i));
        }
        return IDLE_HEIGHTS;
    }

    _repaint(area) {
        let cr = null;
        try {
            const [w, h] = area.get_surface_size();
            cr = area.get_context();
            const [r, g, b] = this._state === 'LISTENING' ? PINK : GREEN;
            cr.setSourceRGBA(r, g, b, 1.0);

            const gap = Math.max(1, Math.round(w * 0.09));
            const barW = (w - gap * (N_BARS - 1)) / N_BARS;
            const padY = Math.round(h * 0.08);
            const maxH = h - padY * 2;
            const baseY = h - padY;
            const rad = Math.min(barW / 2, 3);
            const heights = this._heights();

            for (let i = 0; i < N_BARS; i++) {
                const bh = Math.max(rad * 1.2, clamp(heights[i], 0, 1) * maxH);
                const x = i * (barW + gap);
                const y = baseY - bh;
                this._roundedTopBar(cr, x, y, barW, bh, rad);
                cr.fill();
            }
        } catch (e) {
            logError(e, 'dicti: repaint failed');
        } finally {
            if (cr)
                cr.$dispose();
        }
    }

    // A bar with rounded top corners and a flat bottom (capsule-ish mic feel).
    _roundedTopBar(cr, x, y, w, h, r) {
        const HALF_PI = Math.PI / 2;
        cr.newSubPath();
        cr.arc(x + r, y + r, r, Math.PI, Math.PI + HALF_PI);          // top-left
        cr.arc(x + w - r, y + r, r, Math.PI + HALF_PI, 2 * Math.PI);  // top-right
        cr.lineTo(x + w, y + h);
        cr.lineTo(x, y + h);
        cr.closePath();
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
        this._stopAnim();
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
