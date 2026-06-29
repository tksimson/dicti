#!/usr/bin/env python3
"""
dicti tray indicator (OPTIONAL, for non-GNOME desktops).

On GNOME, prefer the GNOME Shell extension in `gnome-extension/dicti@local`
(installed by `install/07-install-gnome-extension.sh`): it shows a single icon
without pulling in every other app's tray icon. This AppIndicator-based
indicator is kept for KDE/other desktops; it requires `python3-gi` and
`gir1.2-ayatanaappindicator3-0.1`, and on GNOME also the generic AppIndicator
extension. Run it via `dicti-indicator.service` (installed but not enabled by
default).

A small top-bar AppIndicator that mirrors the daemon's dictation state. It
watches $XDG_RUNTIME_DIR/dictation.state (written by the daemon on every
transition) and swaps its icon between idle / listening / processing. The menu
sends START / STOP / TRANSLATE commands to the daemon over its unix socket;
the Translate-to-English check item mirrors the dictation.translate state file.

Runs as a separate user service (dicti-indicator.service) so it can fail and
restart independently of the daemon. Requires PyGObject + an AppIndicator
binding (Ayatana preferred). On GNOME you also need the AppIndicator extension
(appindicatorsupport@rgcjonas.gmail.com or ubuntu-appindicators).
"""

import os
import socket
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator
except (ValueError, ImportError):
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3 as AppIndicator

from gi.repository import Gio, GLib, Gtk

_XDG = os.environ.get("XDG_RUNTIME_DIR")
if not _XDG:
    raise SystemExit("XDG_RUNTIME_DIR not set, indicator must run inside a logind user session")

SOCK_PATH = Path(_XDG) / "dictation.sock"
STATE_PATH = Path(_XDG) / "dictation.state"
TRANSLATE_PATH = Path(_XDG) / "dictation.translate"

# Brand bar-icons (deep green + pink), shipped with the package. The GNOME Shell
# extension draws these animated with Cairo; here (KDE/other) we show the static
# per-state SVG. Referenced by basename via the indicator's icon theme path.
ICON_DIR = Path(__file__).parent / "icons"
ICONS = {
    "IDLE": "dicti-idle",
    "LISTENING": "dicti-listening",
    "PROCESSING": "dicti-processing",
}
LABELS = {
    "IDLE": "Idle",
    "LISTENING": "Listening… (click to stop)",
    "PROCESSING": "Transcribing…",
}


def send_command(cmd: str) -> None:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect(str(SOCK_PATH))
            s.sendall(cmd.encode())
    except OSError as e:
        print(f"dicti-indicator: could not reach daemon: {e}", flush=True)


class Indicator:
    def __init__(self):
        self._state = "IDLE"
        self.ind = AppIndicator.Indicator.new(
            "dicti",
            ICONS["IDLE"],
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        )
        # Resolve our shipped SVGs by basename.
        self.ind.set_icon_theme_path(str(ICON_DIR))
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.ind.set_title("dicti")

        self.status_item = Gtk.MenuItem(label="Idle")
        self.status_item.set_sensitive(False)
        menu = Gtk.Menu()
        menu.append(self.status_item)
        menu.append(Gtk.SeparatorMenuItem())
        # One state-aware item: "Start dictation" when idle (START), "Stop dictation"
        # while listening (STOP). You can't start twice. Greyed while transcribing.
        self.dictate_item = Gtk.MenuItem(label="Start dictation")
        self.dictate_item.connect(
            "activate",
            lambda _: send_command("START" if self._state == "IDLE" else "STOP"))
        menu.append(self.dictate_item)
        menu.append(Gtk.SeparatorMenuItem())
        # Whisper's translate task: speak any language, type English. The check item
        # mirrors the daemon's real state (dictation.translate file); a guard flag stops
        # our own programmatic sync from re-sending TRANSLATE.
        self._translate_syncing = False
        self.translate_item = Gtk.CheckMenuItem(label="Translate to English")
        self.translate_item.connect("toggled", self._on_translate_toggled)
        menu.append(self.translate_item)
        menu.append(Gtk.SeparatorMenuItem())
        self._add_action(menu, "Quit indicator", lambda _: Gtk.main_quit())
        menu.show_all()
        self.ind.set_menu(menu)

        self._apply_state(self._read_state())
        self._apply_translate(self._read_translate())
        self._watch_state_file()

    def _add_action(self, menu, label, cb):
        item = Gtk.MenuItem(label=label)
        item.connect("activate", cb)
        menu.append(item)

    def _read_state(self) -> str:
        try:
            return STATE_PATH.read_text().strip() or "IDLE"
        except OSError:
            return "IDLE"

    def _read_translate(self) -> bool:
        try:
            return TRANSLATE_PATH.read_text().strip() == "ON"
        except OSError:
            return False

    def _apply_state(self, state: str):
        self._state = state
        icon = ICONS.get(state, ICONS["IDLE"])
        self.ind.set_icon_full(icon, state.title())
        self.status_item.set_label(LABELS.get(state, state))
        # IDLE -> "Start dictation"; otherwise "Stop dictation"; greyed while transcribing.
        self.dictate_item.set_label(
            "Start dictation" if state == "IDLE" else "Stop dictation")
        self.dictate_item.set_sensitive(state != "PROCESSING")

    def _apply_translate(self, on: bool):
        if self.translate_item.get_active() == on:
            return
        # setting active fires "toggled"; guard so we don't echo a command back
        self._translate_syncing = True
        self.translate_item.set_active(on)
        self._translate_syncing = False

    def _on_translate_toggled(self, _item):
        if self._translate_syncing:
            return
        send_command("TRANSLATE")

    def _watch_state_file(self):
        gfile = Gio.File.new_for_path(str(STATE_PATH))
        self.monitor = gfile.monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.monitor.connect("changed", self._on_changed)
        # Safety net: also poll every 2s in case inotify misses a tmpfs event.
        GLib.timeout_add_seconds(2, self._poll)

    def _on_changed(self, *_args):
        self._apply_state(self._read_state())
        self._apply_translate(self._read_translate())

    def _poll(self):
        self._apply_state(self._read_state())
        self._apply_translate(self._read_translate())
        return True


def main() -> None:
    Indicator()
    Gtk.main()


if __name__ == "__main__":
    main()
