#!/usr/bin/env python3
"""Spike: a transparent passthrough IBus engine for dicti (spec 0002).

Goal of the spike: prove two things before committing to the IBus path.
  1. TRANSPARENCY: with this engine active, physical typing is unchanged, including the
     user's Polish XKB layout and dead keys. Achieved by layout="default" (inherit the
     user's layout) + do_process_key_event returning False (forward every key to the app).
  2. INJECTION: the dicti daemon can commit dictated UTF-8 text into whatever app is
     focused (editor, terminal, or an integrated terminal like Zed) with no paste shortcut
     and no clipboard. Achieved by commit_text on the focused engine instance.

Run standalone (registers the engine dynamically with the running ibus-daemon):
    python3 dicti_ibus.py
Then add ('ibus','dicti') to org.gnome.desktop.input-sources and make it active.

The daemon talks to this process over a unix socket: send a UTF-8 line, it commit_text's it.
"""

import os
import socket
import threading

import gi

gi.require_version("IBus", "1.0")
from gi.repository import IBus, GLib, GObject  # noqa: E402

SOCK = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "dicti-ibus.sock")

# The currently focused engine instance is the one we commit into.
_current = None


class DictiEngine(IBus.Engine):
    __gtype_name__ = "DictiEngine"

    def do_process_key_event(self, keyval, keycode, state):
        return False  # passthrough: let the application handle every keystroke normally

    def do_focus_in(self):
        global _current
        _current = self

    def do_focus_out(self):
        global _current
        if _current is self:
            _current = None


def _commit(text):
    if _current is not None and text:
        _current.commit_text(IBus.Text.new_from_string(text))
    return False  # for idle_add: run once


def _socket_server():
    try:
        os.unlink(SOCK)
    except OSError:
        pass
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCK)
    os.chmod(SOCK, 0o600)
    srv.listen(4)
    while True:
        conn, _ = srv.accept()
        try:
            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            text = data.decode("utf-8", "replace")
            if text:
                GLib.idle_add(_commit, text)  # commit on the GLib main thread
        finally:
            conn.close()


def main():
    IBus.init()
    bus = IBus.Bus()
    if not bus.is_connected():
        raise SystemExit("ibus-daemon is not connected")
    bus.connect("disconnected", lambda *a: GLib.MainLoop().quit())

    factory = IBus.Factory.new(bus.get_connection())
    factory.add_engine("dicti", DictiEngine.__gtype__)

    component = IBus.Component(
        name="org.freedesktop.IBus.Dicti",
        description="dicti dictation passthrough engine",
        version="0.0.1",
        license="MIT",
        author="dicti",
        homepage="https://github.com/tksimson/dicti",
        command_line="",
        textdomain="dicti",
    )
    desc = IBus.EngineDesc(
        name="dicti",
        longname="Dicti Dictation",
        description="Transparent passthrough that injects dictated text",
        language="en",
        license="MIT",
        author="dicti",
        icon="audio-input-microphone",
        layout="default",  # inherit the user's XKB layout (Polish etc.), do not force one
    )
    component.add_engine(desc)
    bus.register_component(component)

    threading.Thread(target=_socket_server, daemon=True).start()
    print(f"dicti IBus engine registered; commit socket at {SOCK}", flush=True)
    GLib.MainLoop().run()


if __name__ == "__main__":
    main()
