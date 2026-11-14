#!/usr/bin/env python3
"""Unit tests for reading the highlighted text aloud (src/dicti/speak.py). Pure stdlib,
no audio, no real processes.
Run with:  python3 tests/test_speak.py
"""

import os
import subprocess
import sys
import tempfile
import types

os.environ["XDG_RUNTIME_DIR"] = tempfile.mkdtemp()  # never the session's real state files
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import dicti.memo as memo  # noqa: E402
import dicti.speak as speak  # noqa: E402


def _fake_subprocess(run=None, popen=None):
    """Stand-in for speak.subprocess, so the stdlib module itself is never patched."""
    return types.SimpleNamespace(run=run, Popen=popen, PIPE=subprocess.PIPE,
                                 DEVNULL=subprocess.DEVNULL,
                                 TimeoutExpired=subprocess.TimeoutExpired)


def test_language_polish_letters():
    assert speak.language("Zażółć gęślą jaźń") == "pl"


def test_language_polish_without_diacritics():
    assert speak.language("To nie jest takie proste, ale tak bywa") == "pl"


def test_language_english():
    assert speak.language("This is a plain English sentence to read aloud.") == "en"
    assert speak.language("to be or not to be") == "en"


def test_sentences_split_at_ends_and_lines():
    assert speak.sentences("Hej! Jak się masz? Dobrze.\n\nNew line… here") == [
        "Hej!", "Jak się masz?", "Dobrze.", "New line…", "here"]
    assert speak.sentences("  \n ") == []


def test_settings_default_and_reject_unknown():
    speak.settings_path().unlink(missing_ok=True)
    assert speak.settings() == {"voice": "F1", "speed": "normal"}
    assert speak.save_setting("voice", "M4") == 0
    assert speak.save_setting("speed", "warp") == 2
    assert speak.settings() == {"voice": "M4", "speed": "normal"}
    speak.settings_path().write_text('{"voice": "X9", "speed": "faster"}')
    assert speak.settings() == {"voice": "F1", "speed": "faster"}
    speak.settings_path().write_text("not json")
    assert speak.settings() == {"voice": "F1", "speed": "normal"}
    speak.settings_path().unlink()


def test_selection_falls_back_to_xclip():
    calls = []

    def run(cmd, **_kw):
        calls.append(cmd[0])
        if cmd[0] == "wl-paste":
            raise FileNotFoundError(cmd[0])
        return types.SimpleNamespace(returncode=0, stdout="  hello  \n")

    real = speak.subprocess
    speak.subprocess = _fake_subprocess(run=run)
    try:
        assert speak.selection() == "hello"
    finally:
        speak.subprocess = real
    assert calls == ["wl-paste", "xclip"]


def test_selection_empty_when_nothing_works():
    real = speak.subprocess
    speak.subprocess = _fake_subprocess(
        run=lambda cmd, **_kw: types.SimpleNamespace(returncode=1, stdout=""))
    try:
        assert speak.selection() == ""
    finally:
        speak.subprocess = real


def test_running_pid_checks_marker():
    pid_file = memo._runtime_dir() / "test-speak.pid"
    pid_file.write_text(f"{os.getpid()}\n")
    try:
        assert memo._running_pid(pid_file, "no-such-marker-xyz") is None
        assert memo._running_pid(pid_file, "python") == os.getpid()
    finally:
        pid_file.unlink()


def test_phase_follows_live_worker_only():
    # Other test modules reassign XDG_RUNTIME_DIR, so paths resolve at call time.
    real = speak.running_pid
    try:
        speak.running_pid = lambda: None   # dead or foreign pid: leftover files are ignored
        speak.phase_path().write_text("SPEAKING\n")
        assert speak.phase() is None
        speak.running_pid = lambda: 4242
        assert speak.phase() == "SPEAKING"
        speak.phase_path().unlink()
        assert speak.phase() == "PREPARING"
    finally:
        speak.running_pid = real
        speak.phase_path().unlink(missing_ok=True)


def test_text_goes_on_stdin_not_argv():
    seen = {}

    class Proc:
        pid = 4242

        def __init__(self, argv, **kw):
            seen["argv"] = argv
            seen["new_session"] = kw.get("start_new_session")
            self.stdin = types.SimpleNamespace(write=lambda b: seen.setdefault("stdin", b),
                                               close=lambda: None)

    real = speak.subprocess
    speak.subprocess = _fake_subprocess(popen=Proc)
    try:
        speak._start("tajny tekst")
    finally:
        speak.subprocess = real
    assert seen["stdin"] == "tajny tekst".encode()
    assert not any("tajny" in a for a in seen["argv"])
    assert seen["new_session"] is True


def test_refuses_while_dictating():
    # Other test modules reassign XDG_RUNTIME_DIR, so resolve it now, not at import.
    state = memo._runtime_dir() / "dictation.state"
    state.write_text("LISTENING\n")
    notes = []
    real = memo._notify, speak.selection, speak._start
    memo._notify = lambda summary, body="", **_kw: notes.append(summary)
    speak.selection = lambda: "should not be read"
    speak._start = lambda *_a: (_ for _ in ()).throw(AssertionError("started speaking"))
    try:
        assert speak.speak_toggle() == 1
    finally:
        memo._notify, speak.selection, speak._start = real
        state.unlink()
    assert notes == ["Not speaking"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
