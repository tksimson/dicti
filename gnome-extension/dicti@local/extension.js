/* dicti dictation, GNOME Shell panel indicator.
 *
 * One custom-drawn icon that mirrors the daemon's state file
 * ($XDG_RUNTIME_DIR/dictation.state). The icon is a set of five bars rendered
 * with Cairo, animated per state (see specs/0001 and design/icon-preview-v3):
 *   IDLE       static "trapezoid" mic silhouette, deep green
 *   LISTENING  organic equalizer bounce (random walk), pink
 *   PROCESSING left->right "fill" progress, deep green
 *   PREPARING  small centred capsules breathing, green (voice loading, reading aloud)
 *   SPEAKING   calm ripple out from the middle bar, green (reading aloud)
 * Mic states grow from the floor (sound in); speak states grow from the midline
 * (sound out). Pink is kept for "the mic is live".
 *
 * A click opens the menu: Start / Stop dictation plus a "Translate to English"
 * switch (mirrors $XDG_RUNTIME_DIR/dictation.translate). No AppIndicator needed,
 * so no other apps' tray icons are pulled in.
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

// Reading aloud (design: speak-ux mockups). Times in ms.
const SPEAK_PERIOD = 960;   // one outward ripple
const SPEAK_LAG = 110;      // per bar away from the centre, so the middle leads
const SPEAK_MIN = 0.22;
const SPEAK_AMP = [0.50, 0.75, 1.00, 0.75, 0.50];
const PREP_PERIOD = 1400;   // one breath
const PREP_LAG = 60;
const PREP_LO = 0.18, PREP_HI = 0.38;
const PREP_ALPHA_LO = 0.55;
const SPEAK_STATES = ['PREPARING', 'SPEAKING'];
const DICTI = `${GLib.get_home_dir()}/.local/bin/dicti`;
// Reading-aloud choices, saved by `dicti --speak-voice/--speak-speed` (src/dicti/speak.py).
const SPEAK_VOICES = [['F1', 'Female 1'], ['F3', 'Female 2'], ['M1', 'Male 1'], ['M4', 'Male 2']];
const SPEAK_SPEEDS = [['slower', 'Slower'], ['normal', 'Normal'], ['faster', 'Faster']];
const SPEAK_DEFAULTS = {voice: 'F1', speed: 'normal'};

function clamp(v, lo, hi) {
    return v < lo ? lo : v > hi ? hi : v;
}

// 0..1..0 cosine wave for bar i, delayed by its distance from the centre bar.
function centreWave(nowMs, i, period, lag) {
    const ph = (nowMs - Math.abs(i - 2) * lag) / period;
    return 0.5 - 0.5 * Math.cos(2 * Math.PI * ph);
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

        // One item that follows the daemon state: "Start dictation" when idle (sends
        // START), "Stop dictation" while listening (sends STOP). You can't start twice,
        // so a single state-aware item is clearer than two. Greyed while transcribing.
        this._dictateItem = new PopupMenu.PopupMenuItem('Start dictation');
        this._dictateItem.connect('activate', () => {
            if (this._memoRecording())     // "Stop" during an mp3 recording = stop + save it
                GLib.spawn_command_line_async(`${DICTI} --memo-toggle`);
            else if (SPEAK_STATES.includes(this._state))    // "Stop reading"
                GLib.spawn_command_line_async(`${DICTI} --speak-toggle`);
            else
                this._send(this._state === 'IDLE' ? 'START' : 'STOP');
        });
        this.menu.addMenuItem(this._dictateItem);

        // The way in without a Copilot key; only shown when idle. Opening the menu keeps
        // the primary selection, so the highlighted text is still there.
        this._readItem = new PopupMenu.PopupMenuItem('Read highlighted text');
        this._readItem.connect('activate',
            () => GLib.spawn_command_line_async(`${DICTI} --speak-toggle`));
        this.menu.addMenuItem(this._readItem);

        // Voice and speed for reading aloud; the check marks follow speak.json on each open.
        this._speakChoices = {};
        for (const [key, title, options] of [['voice', 'Voice', SPEAK_VOICES],
            ['speed', 'Speed', SPEAK_SPEEDS]]) {
            const sub = new PopupMenu.PopupSubMenuMenuItem(title);
            this._speakChoices[key] = options.map(([value, label]) => {
                const item = sub.menu.addAction(label, () => GLib.spawn_command_line_async(
                    `${DICTI} --speak-${key} ${value}`));
                return [value, item];
            });
            this.menu.addMenuItem(sub);
        }
        this.menu.connect('open-state-changed', (_m, open) => {
            if (open)
                this._updateSpeakChoices();
        });

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        // Whisper's translate task: speak any language, type English. The switch
        // reflects the daemon's real state (dictation.translate file), so an external
        // `dictate-translate` or a config default keeps it in sync. 'toggled' fires on
        // user click only (programmatic setToggleState doesn't), so no feedback loop.
        this._translateItem = new PopupMenu.PopupSwitchMenuItem(
            'Translate to English', false);
        this._translateItem.connect('toggled', () => this._send('TRANSLATE'));
        this.menu.addMenuItem(this._translateItem);

        // A click just opens the menu (PanelMenu.Button's default), so dictation is
        // only ever started/stopped from the explicit menu items, never by a stray click.

        this._statePath = GLib.build_filenamev(
            [GLib.get_user_runtime_dir(), 'dictation.state']);
        this._file = Gio.File.new_for_path(this._statePath);
        try {
            this._monitor = this._file.monitor(Gio.FileMonitorFlags.NONE, null);
            this._monitorId = this._monitor.connect('changed', () => this._update());
        } catch (e) {
            logError(e, 'dicti: could not watch state file');
        }

        this._translatePath = GLib.build_filenamev(
            [GLib.get_user_runtime_dir(), 'dictation.translate']);
        this._translateFile = Gio.File.new_for_path(this._translatePath);
        try {
            this._translateMonitor =
                this._translateFile.monitor(Gio.FileMonitorFlags.NONE, null);
            this._translateMonitorId = this._translateMonitor.connect(
                'changed', () => this._updateTranslate());
        } catch (e) {
            logError(e, 'dicti: could not watch translate file');
        }

        // Poll as a safety net (tmpfs inotify can be flaky).
        this._pollId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 2, () => {
            this._update();
            this._updateTranslate();
            return GLib.SOURCE_CONTINUE;
        });

        this._update();
        this._updateTranslate();
        this._area.queue_repaint();   // draw the idle mark once on startup
    }

    _updateTranslate() {
        let on = false;
        try {
            const [ok, contents] = GLib.file_get_contents(this._translatePath);
            if (ok)
                on = (new TextDecoder().decode(contents)).trim() === 'ON';
        } catch (e) {
            // file may not exist yet -> treat as off
        }
        if (this._translateItem && this._translateItem.state !== on)
            this._translateItem.setToggleState(on);
    }

    _updateSpeakChoices() {
        let saved = {};
        try {
            const [ok, contents] = GLib.file_get_contents(GLib.build_filenamev(
                [GLib.get_user_config_dir(), 'dicti', 'speak.json']));
            if (ok)
                saved = JSON.parse(new TextDecoder().decode(contents)) ?? {};
        } catch (e) {
            // nothing chosen yet: defaults
        }
        for (const [key, items] of Object.entries(this._speakChoices)) {
            const values = items.map(([v]) => v);
            const current = values.includes(saved[key]) ? saved[key] : SPEAK_DEFAULTS[key];
            for (const [value, item] of items) {
                item.setOrnament(value === current     // radio-style, like GNOME's own
                    ? PopupMenu.Ornament.DOT : PopupMenu.Ornament.NO_DOT);
            }
        }
    }

    // A pidfile only counts while that PID is alive with `marker` in its cmdline, so a
    // stale file (killed process, reused PID) never sticks the icon.
    _ownedPid(name, marker) {
        try {
            const [ok, pid] = GLib.file_get_contents(GLib.build_filenamev(
                [GLib.get_user_runtime_dir(), name]));
            const p = ok ? new TextDecoder().decode(pid).trim() : '';
            if (!/^\d+$/.test(p))
                return false;
            const [ok2, cmd] = GLib.file_get_contents(`/proc/${p}/cmdline`);
            return ok2 && new TextDecoder().decode(cmd).includes(marker);
        } catch (e) {
            return false;
        }
    }

    // An mp3 recording (`dicti --memo-toggle`) shows as LISTENING.
    _memoRecording() {
        return this._ownedPid('dicti-memo.pid', 'pw-record');
    }

    // Reading aloud (`dicti --speak-toggle`): PREPARING until the worker writes SPEAKING
    // to dicti-speak.phase at the first sound; null when not reading.
    _speakPhase() {
        if (!this._ownedPid('dicti-speak.pid', 'dicti.tts_worker'))
            return null;
        try {
            const [ok, contents] = GLib.file_get_contents(GLib.build_filenamev(
                [GLib.get_user_runtime_dir(), 'dicti-speak.phase']));
            if (ok && new TextDecoder().decode(contents).trim() === 'SPEAKING')
                return 'SPEAKING';
        } catch (e) {
            // no phase file yet = still getting the voice ready
        }
        return 'PREPARING';
    }

    _readState() {
        if (this._memoRecording())
            return 'LISTENING';
        let state = 'IDLE';
        try {
            const [ok, contents] = GLib.file_get_contents(this._statePath);
            if (ok)
                state = (new TextDecoder().decode(contents)).trim() || 'IDLE';
        } catch (e) {
            // file may not exist yet
        }
        return state !== 'IDLE' ? state : (this._speakPhase() ?? 'IDLE');
    }

    _updateDictateItem() {
        if (!this._dictateItem)
            return;
        // IDLE -> "Start dictation"; LISTENING -> "Stop dictation"; PROCESSING ->
        // greyed (recording already stopped, transcription in flight, nothing to do).
        // Reading aloud -> "Stop reading".
        const speaking = SPEAK_STATES.includes(this._state);
        this._dictateItem.label.text = this._state === 'IDLE' ? 'Start dictation'
            : speaking ? 'Stop reading' : 'Stop dictation';
        this._dictateItem.setSensitive(this._state !== 'PROCESSING');
        this._readItem.visible = this._state === 'IDLE';
    }

    _update() {
        const state = this._readState();
        if (state === this._state)
            return;                            // no transition: nothing to redraw
        this._state = state;
        this._updateDictateItem();
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
        const now = GLib.get_monotonic_time() / 1000;
        if (this._state === 'PROCESSING')
            return Array.from({length: N_BARS}, (_, i) => fillHeight(now, i));
        if (this._state === 'PREPARING') {
            return Array.from({length: N_BARS}, (_, i) =>
                PREP_LO + (PREP_HI - PREP_LO) * centreWave(now, i, PREP_PERIOD, PREP_LAG));
        }
        if (this._state === 'SPEAKING') {
            return Array.from({length: N_BARS}, (_, i) => SPEAK_MIN +
                SPEAK_AMP[i] * (1 - SPEAK_MIN) * centreWave(now, i, SPEAK_PERIOD, SPEAK_LAG));
        }
        return IDLE_HEIGHTS;
    }

    // Preparing breathes in opacity as well as height; everything else is opaque.
    _alpha(i) {
        if (this._state !== 'PREPARING')
            return 1.0;
        const now = GLib.get_monotonic_time() / 1000;
        return PREP_ALPHA_LO + (1 - PREP_ALPHA_LO) * centreWave(now, i, PREP_PERIOD, PREP_LAG);
    }

    _repaint(area) {
        let cr = null;
        try {
            const [w, h] = area.get_surface_size();
            cr = area.get_context();
            const [r, g, b] = this._state === 'LISTENING' ? PINK : GREEN;
            const centred = SPEAK_STATES.includes(this._state);

            const gap = Math.max(1, Math.round(w * 0.09));
            const barW = (w - gap * (N_BARS - 1)) / N_BARS;
            const padY = Math.round(h * 0.08);
            const maxH = h - padY * 2;
            const baseY = h - padY;
            const rad = Math.min(barW / 2, 3);
            const heights = this._heights();

            for (let i = 0; i < N_BARS; i++) {
                cr.setSourceRGBA(r, g, b, this._alpha(i));
                const bh = Math.max(rad * 1.2, clamp(heights[i], 0, 1) * maxH);
                const x = i * (barW + gap);
                if (centred)    // sound out: grows both ways from the midline
                    this._capsule(cr, x, h / 2 - bh / 2, barW, Math.max(bh, barW), barW / 2);
                else
                    this._roundedTopBar(cr, x, baseY - bh, barW, bh, rad);
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

    // A bar rounded at both ends (the speak states). Needs h >= 2r.
    _capsule(cr, x, y, w, h, r) {
        cr.newSubPath();
        cr.arc(x + r, y + r, r, Math.PI, 2 * Math.PI);
        cr.arc(x + w - r, y + h - r, r, 0, Math.PI);
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
        if (this._translateMonitor) {
            if (this._translateMonitorId)
                this._translateMonitor.disconnect(this._translateMonitorId);
            this._translateMonitor.cancel();
            this._translateMonitor = null;
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
