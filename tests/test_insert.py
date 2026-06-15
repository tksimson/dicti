#!/usr/bin/env python3
"""Unit tests for the insertion backends (src/dicti/insert.py, spec 0001).

Pure stdlib. Patches the module's low-level helpers so no real keystrokes/clipboard happen.
Run with:  python3 tests/test_insert.py
"""

import os
import sys
import tempfile

os.environ.setdefault("XDG_RUNTIME_DIR", tempfile.mkdtemp())
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import dicti.insert as ins  # noqa: E402
from dicti.config import Config  # noqa: E402


def _cfg(**kw):
    c = Config()
    for k, v in kw.items():
        setattr(c, k, v)
    return c


class _FakeClip:
    def __init__(self, value=b"ORIG"):
        self.value = value
        self.sets = []
        self.gets = 0

    def get(self):
        self.gets += 1
        return self.value

    def set(self, text):
        self.sets.append(text)

    def set_bytes(self, data):
        self.sets.append(data)


def _patch(monkey_terminal=False):
    """Patch helpers; return a list that records (kind, payload)."""
    rec = []
    ins._ydotool_type = lambda text, delay: rec.append(("type", text))
    ins._ydotool_key = lambda keys: rec.append(("key", keys))
    ins._active_window_is_terminal = lambda: monkey_terminal
    ins.time.sleep = lambda s: None
    return rec


def test_make_inserter_default_is_clipboard():
    ins.is_wayland = lambda: False
    assert ins.make_inserter(_cfg()).name == "clipboard"


def test_make_inserter_wtype_on_wlroots():
    ins.is_wayland = lambda: True
    ins.is_wlroots = lambda: True
    ins.shutil.which = lambda b: "/usr/bin/wtype" if b == "wtype" else None
    assert ins.make_inserter(_cfg(insert_backend="auto")).name == "wtype"


def test_make_inserter_explicit_ydotool():
    assert ins.make_inserter(_cfg(insert_backend="ydotool")).name == "ydotool"


def test_make_inserter_ibus_falls_back_to_clipboard():
    assert ins.make_inserter(_cfg(insert_backend="ibus")).name == "clipboard"


def test_ascii_types_nonascii_pastes():
    rec = _patch()
    it = ins.ClipboardInserter(_cfg(paste_keys="ctrl+v"))
    it.clip = _FakeClip()
    it.insert("hello world")
    it.insert("Cześć")
    kinds = [r[0] for r in rec]
    assert kinds == ["type", "key"], rec          # ascii typed, polish pasted (one key event)
    assert it.clip.sets[0] == "Cześć"             # exact text went to the clipboard


def test_paste_keys_modes():
    for mode, want in [("ctrl+v", ins._KEYS_CTRL_V),
                       ("ctrl+shift+v", ins._KEYS_CTRL_SHIFT_V)]:
        rec = _patch()
        it = ins.ClipboardInserter(_cfg(paste_keys=mode))
        it.clip = _FakeClip()
        it.insert("ą")
        assert ("key", want) in rec, (mode, rec)
    # auto -> terminal detection drives the choice
    rec = _patch(monkey_terminal=True)
    it = ins.ClipboardInserter(_cfg(paste_keys="auto"))
    it.clip = _FakeClip()
    it.insert("ą")
    assert ("key", ins._KEYS_CTRL_SHIFT_V) in rec


def test_clipboard_saved_lazily_once_and_restored():
    rec = _patch()
    it = ins.ClipboardInserter(_cfg(paste_keys="ctrl+v"))
    it.clip = _FakeClip(value=b"USER-CLIP")
    it.insert("alpha")          # ascii: must NOT read the clipboard
    assert it.clip.gets == 0
    it.insert("ą")              # first paste: saves once
    it.insert("ę")             # second paste: does not save again
    assert it.clip.gets == 1
    it.end_session("alpha ą ę", preserve_clipboard=True)
    assert it.clip.sets[-1] == b"USER-CLIP"   # original restored


def test_preserve_false_leaves_transcript():
    rec = _patch()
    it = ins.ClipboardInserter(_cfg(paste_keys="ctrl+v"))
    it.clip = _FakeClip()
    it.insert("ą")
    it.end_session("the transcript", preserve_clipboard=False)
    assert it.clip.sets[-1] == "the transcript"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"\n{len(tests)} insertion tests passed")
