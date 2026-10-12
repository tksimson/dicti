#!/usr/bin/env python3
"""Unit tests for audio memos (src/dicti/memo.py). Pure stdlib, no audio, no processes.
Run with:  python3 tests/test_memo.py
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("XDG_RUNTIME_DIR", tempfile.mkdtemp())
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import dicti.memo as memo  # noqa: E402

CWD = Path("/work")


def test_target_path_adds_suffix_in_cwd():
    assert memo.target_path("notes", CWD) == CWD / "notes.mp3"
    assert memo.target_path("notes.MP3", CWD) == CWD / "notes.MP3"


def test_target_path_drops_leading_dashes():
    assert memo.target_path("-notes", CWD) == CWD / "notes.mp3"


def test_target_path_keeps_absolute_and_dotted_names():
    assert memo.target_path("/tmp/a.b", CWD) == Path("/tmp/a.b.mp3")


def test_target_path_rejects_empty():
    try:
        memo.target_path("--", CWD)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_save_dir_prefers_last_dir():
    last = Path(tempfile.mkdtemp())
    memo._last_dir_path().parent.mkdir(parents=True, exist_ok=True)
    memo._last_dir_path().write_text(f"{last}\n")
    assert memo.save_dir() == last


def test_save_dir_skips_vanished_last_dir():
    memo._last_dir_path().parent.mkdir(parents=True, exist_ok=True)
    memo._last_dir_path().write_text("/no/such/dir\n")
    assert memo.save_dir() != Path("/no/such/dir")


def test_running_pid_ignores_foreign_process():
    memo._pid_path().write_text(f"{os.getpid()}\n")  # alive, but not a pw-record pipeline
    try:
        assert memo.running_pid() is None
    finally:
        memo._pid_path().unlink(missing_ok=True)


def test_running_pid_ignores_garbage():
    memo._pid_path().write_text("not a pid\n")
    try:
        assert memo.running_pid() is None
    finally:
        memo._pid_path().unlink(missing_ok=True)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"\n{len(tests)} memo tests passed")
