"""Text insertion backends for dicti (see specs/0001-text-insertion.md).

Inserting transcribed text into the focused window is the hardest cross-desktop problem in
the project. No keystroke injector types arbitrary Unicode everywhere:
  - ydotool (uinput): universal, but ASCII only (layout-blind, drops Polish ąęóśżźćń);
  - xdotool (X11 XTEST): types Unicode but its live keymap remap froze our X server (banned);
  - wtype (Wayland virtual-keyboard): types Unicode but only on wlroots (Sway/Hyprland);
  - clipboard-paste: the only universal full-Unicode path.

So the universal default is: type ASCII via ydotool, paste non-ASCII via the clipboard
(xclip on X11, wl-clipboard on Wayland), choosing the paste shortcut from the focused window.
On wlroots, wtype types everything natively. Backends are chosen by capability detection.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time

log = logging.getLogger("dictation.insert")

# Terminals paste with Ctrl+Shift+V (Ctrl+V is "literal next char" there); almost every other
# app pastes with Ctrl+V. We pick per focused-window WM_CLASS, matching substrings so variants
# are covered (gnome-terminal-server, xfce4-terminal, org.gnome.Console/kgx, ...).
_TERMINAL_WM_HINTS = (
    "terminal", "konsole", "xterm", "rxvt", "alacritty", "kitty", "wezterm",
    "foot", "tilix", "guake", "yakuake", "terminator", "termite", "sakura",
    "org.gnome.console", "kgx", "io.elementary.terminal", "contour", "st-256color",
)
# ydotool key sequences. KEY_LEFTCTRL=29, KEY_LEFTSHIFT=42, KEY_V=47.
_KEYS_CTRL_V = ["29:1", "47:1", "47:0", "29:0"]
_KEYS_CTRL_SHIFT_V = ["29:1", "42:1", "47:1", "47:0", "42:0", "29:0"]


def is_wayland() -> bool:
    return (os.environ.get("XDG_SESSION_TYPE") == "wayland"
            or bool(os.environ.get("WAYLAND_DISPLAY")))


def is_wlroots() -> bool:
    """Heuristic: a wlroots-based compositor (where wtype works). GNOME/KDE are excluded."""
    desk = (os.environ.get("XDG_CURRENT_DESKTOP", "") + ";"
            + os.environ.get("XDG_SESSION_DESKTOP", "")).lower()
    return any(c in desk for c in ("sway", "hyprland", "wlroots", "river", "wayfire", "labwc"))


# ---- low-level helpers -------------------------------------------------------

def _ydotool_type(text: str, key_delay_ms: int) -> None:
    # --file - reads stdin with escapes disabled, so newlines and UTF-8 bytes pass literally.
    subprocess.run(
        ["ydotool", "type", "--key-delay", str(key_delay_ms), "--file", "-"],
        input=text.encode("utf-8"), check=True, timeout=60,
    )


def _ydotool_key(keys: list[str]) -> None:
    subprocess.run(["ydotool", "key", *keys], check=True, timeout=2)


def _active_window_is_terminal() -> bool:
    """True if the focused window looks like a terminal (paste = Ctrl+Shift+V). Reads WM_CLASS
    via xprop, a harmless X11 query that never remaps the keymap. Returns False (= Ctrl+V) on
    Wayland or any failure, correct for the large majority of apps."""
    if not shutil.which("xprop"):
        return False
    try:
        root = subprocess.run(["xprop", "-root", "_NET_ACTIVE_WINDOW"],
                              capture_output=True, text=True, timeout=1).stdout
        wid = root.strip().split()[-1]
        if not wid.startswith("0x"):
            return False
        out = subprocess.run(["xprop", "-id", wid, "WM_CLASS"],
                             capture_output=True, text=True, timeout=1).stdout.lower()
    except Exception:
        return False
    return any(hint in out for hint in _TERMINAL_WM_HINTS)


class _Clipboard:
    """Read/write the system clipboard: wl-clipboard on Wayland, else xclip."""

    def __init__(self) -> None:
        if is_wayland() and shutil.which("wl-copy"):
            self.kind = "wl"
        else:
            self.kind = "x"

    def set_bytes(self, data: bytes) -> None:
        cmd = ["wl-copy"] if self.kind == "wl" else ["xclip", "-selection", "clipboard"]
        try:
            subprocess.run(cmd, input=data, check=True, timeout=2)
        except Exception as e:
            log.warning("clipboard set failed: %s", e)

    def set(self, text: str) -> None:
        self.set_bytes(text.encode("utf-8"))

    def get(self) -> bytes | None:
        cmd = (["wl-paste", "-n"] if self.kind == "wl"
               else ["xclip", "-selection", "clipboard", "-o"])
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=2)
            return r.stdout if r.returncode == 0 else None
        except Exception:
            return None


# ---- backends ----------------------------------------------------------------

class Inserter:
    name = "base"

    def insert(self, text: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def end_session(self, transcript: str, preserve_clipboard: bool) -> None:
        """Called once when a dictation session ends, for clipboard etiquette."""


class ClipboardInserter(Inserter):
    """Universal default: type ASCII via ydotool, paste non-ASCII via the clipboard.

    The user's clipboard is saved lazily before the first paste and, by default, restored
    when the session ends (preserve_clipboard). With preserve_clipboard=False the full
    transcript is left on the clipboard as a re-paste safety net."""

    name = "clipboard"

    def __init__(self, cfg) -> None:
        self.cfg = cfg
        self.clip = _Clipboard()
        self._saved: bytes | None = None
        self._saved_done = False

    def insert(self, text: str) -> None:
        if not text:
            return
        if text.isascii():
            _ydotool_type(text, self.cfg.key_delay_ms)
        else:
            self._paste(text)

    def _paste(self, text: str) -> None:
        if not self._saved_done:           # remember the user's clipboard once per session
            self._saved = self.clip.get()
            self._saved_done = True
        self.clip.set(text)
        time.sleep(0.05)                   # let the clipboard settle
        _ydotool_key(_KEYS_CTRL_SHIFT_V if self._terminal() else _KEYS_CTRL_V)
        time.sleep(0.1)                    # let the app read it before we touch it again

    def _terminal(self) -> bool:
        mode = self.cfg.paste_keys
        if mode == "ctrl+v":
            return False
        if mode == "ctrl+shift+v":
            return True
        return _active_window_is_terminal()  # "auto"

    def end_session(self, transcript: str, preserve_clipboard: bool) -> None:
        if preserve_clipboard:
            if self._saved_done:
                self.clip.set_bytes(self._saved or b"")
        elif transcript:
            self.clip.set(transcript)
        self._saved, self._saved_done = None, False


class WtypeInserter(Inserter):
    """wlroots only: wtype types arbitrary Unicode natively, so no clipboard or paste keys."""

    name = "wtype"

    def __init__(self, cfg) -> None:
        self.cfg = cfg

    def insert(self, text: str) -> None:
        if not text:
            return
        # wtype types its argument literally. "--" guards a leading dash.
        subprocess.run(["wtype", "--", text], check=True, timeout=60)

    def end_session(self, transcript: str, preserve_clipboard: bool) -> None:
        if not preserve_clipboard and transcript:
            _Clipboard().set(transcript)


class YdotoolInserter(Inserter):
    """ASCII-only typing via ydotool. Explicit fallback; drops non-ASCII characters."""

    name = "ydotool"

    def __init__(self, cfg) -> None:
        self.cfg = cfg

    def insert(self, text: str) -> None:
        if text:
            _ydotool_type(text, self.cfg.key_delay_ms)

    def end_session(self, transcript: str, preserve_clipboard: bool) -> None:
        if not preserve_clipboard and transcript:
            _Clipboard().set(transcript)


def make_inserter(cfg) -> Inserter:
    """Pick an insertion backend from config + environment capabilities."""
    backend = getattr(cfg, "insert_backend", "auto")
    if backend == "auto":
        if is_wayland() and is_wlroots() and shutil.which("wtype"):
            backend = "wtype"
        else:
            backend = "clipboard"
    if backend == "wtype" and shutil.which("wtype"):
        return WtypeInserter(cfg)
    if backend == "ydotool":
        return YdotoolInserter(cfg)
    if backend == "ibus":
        log.warning("insert_backend=ibus not implemented yet (spec 0002); using clipboard")
    return ClipboardInserter(cfg)
