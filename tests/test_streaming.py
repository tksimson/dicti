#!/usr/bin/env python3
"""Unit tests for v0.3 streaming (mode == "streaming").

Growing-window re-transcription: each pass transcribes the whole utterance so far and
appends only words that have stabilised across passes (append-only). Pure stdlib: stubs
`requests`, points XDG at a temp dir, drives the commit logic directly. Run with:

    python3 tests/test_streaming.py
"""

import io
import os
import sys
import tempfile
import types
import wave
from pathlib import Path

# --- stub requests so no whisper-server is needed ------------------------------
_req = types.ModuleType("requests")


class _Resp:
    def __init__(self, text):
        self._t = text

    def raise_for_status(self):
        pass

    def json(self):
        return {"text": self._t}


_req.next_text = ""
_req.post = lambda url, files=None, data=None, timeout=None: _Resp(_req.next_text)
sys.modules["requests"] = _req

# --- isolate XDG + import ------------------------------------------------------
_tmp = tempfile.mkdtemp()
os.environ["XDG_RUNTIME_DIR"] = _tmp
os.environ["XDG_CONFIG_HOME"] = _tmp
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dicti.daemon import Daemon, _common_prefix, SAMPLE_RATE  # noqa: E402
from dicti.config import Config  # noqa: E402


class _FakeInserter:
    """Records inserted pieces; no ydotool/clipboard side effects."""
    name = "fake"

    def __init__(self):
        self.typed = []

    def insert(self, text):
        self.typed.append(text)

    def end_session(self, transcript, preserve_clipboard):
        pass


def _new_daemon():
    cfg = Config()
    cfg.mode = "streaming"
    d = Daemon(cfg)
    d.inserter = _FakeInserter()
    d.typed = d.inserter.typed
    return d


def _commit_pass(d, words):
    """Simulate one stream-loop commit step: emit the words newly stable vs displayed."""
    stable = words  # caller passes the already-computed stable prefix
    if len(stable) > len(d._displayed_words):
        d._emit_words(stable[len(d._displayed_words):])
        d._displayed_words = stable


def test_common_prefix():
    assert _common_prefix("a b c".split(), "a b x".split()) == ["a", "b"]
    assert _common_prefix("a b".split(), "x".split()) == []
    assert _common_prefix([], ["a"]) == []
    assert _common_prefix("one two".split(), "one two three".split()) == ["one", "two"]


def test_growing_window_append_only():
    # Three passes of a growing utterance; only stable words get typed, with separators.
    d = _new_daemon()
    prev = []
    typed_log = []
    for words in [
        "And so".split(),
        "And so my fellow".split(),
        "And so my fellow Americans".split(),
    ]:
        stable = _common_prefix(words, prev)
        _commit_pass(d, stable)
        prev = words
    # "And so" stabilised on pass 2, "my fellow" on pass 3; "Americans" not yet.
    assert d._session_text == "And so my fellow", d._session_text
    assert d.typed[0] == "And so"          # first emit: no leading space
    assert all(p.startswith(" ") for p in d.typed[1:]), d.typed  # later emits: leading space


def test_displayed_never_shrinks():
    # If a later pass disagrees about an already-typed word, we keep what we typed
    # (append-only) and never un-type or duplicate.
    d = _new_daemon()
    _commit_pass(d, "hello world".split())
    before = list(d.typed)
    # a pass whose stable prefix is shorter must not retype or delete
    stable = _common_prefix("hello".split(), "hello".split())  # ["hello"], shorter
    _commit_pass(d, stable)
    assert d.typed == before, d.typed
    assert d._session_text == "hello world"


def test_final_flush_types_tail():
    # Stream loop committed "alpha beta"; the final full-context pass yields one more word.
    d = _new_daemon()
    _commit_pass(d, "alpha beta".split())
    _req.next_text = "alpha beta gamma"
    # no audio file -> _read_pcm returns b"" -> words=[]; so give it a window
    with wave.open(_wav_path(), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SAMPLE_RATE)
        w.writeframes(b"\x10\x00" * SAMPLE_RATE)  # 1s of audio so _read_pcm has data
    d._anchor_byte = 0
    d._final_flush(Path(_wav_path()))
    assert d._session_text == "alpha beta gamma", d._session_text
    assert d.typed[-1] == " gamma", d.typed


def test_final_flush_reuses_in_flight_pass():
    """When a pass already covers the recording, STOP must not pay for a second inference."""
    d = _new_daemon()
    _commit_pass(d, "alpha beta".split())
    with wave.open(_wav_path(), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SAMPLE_RATE)
        w.writeframes(b"\x10\x00" * SAMPLE_RATE)
    end = d._data_end()
    d._anchor_byte = 0
    d._last_pass = (0, end, "alpha beta gamma".split())
    d._pass_done.set()
    calls = []
    d._transcribe_pcm = lambda pcm: calls.append(pcm) or "SHOULD NOT BE USED"
    d._final_flush(Path(_wav_path()))
    assert calls == [], "final flush re-transcribed audio a pass already covered"
    assert d.typed[-1] == " gamma", d.typed


def test_final_flush_transcribes_when_audio_grew():
    """A pass that predates the last spoken words must not be reused."""
    d = _new_daemon()
    _commit_pass(d, "alpha".split())
    _write_wav(loud_sec=3.0)
    d._anchor_byte = 0
    d._last_pass = (0, 100, "alpha".split())  # stale: covers a fraction of the audio
    d._pass_done.set()
    _req.next_text = "alpha beta"
    d._final_flush(Path(_wav_path()))
    assert d._session_text == "alpha beta", d._session_text


def test_final_flush_reuses_a_pass_when_the_tail_is_silence():
    """You stop talking, then reach for the key. Re-transcribing the whole window over those
    few seconds of silence returns the identical words and used to cost 4s+ of PROCESSING."""
    d = _new_daemon()
    _commit_pass(d, "alpha beta".split())
    _write_wav(loud_sec=1.0, quiet_sec=3.0)   # spoke for 1s, then 3s of reaching for the key
    d._anchor_byte = 0
    speech_end = SAMPLE_RATE * 2              # the pass saw everything up to the silence
    d._last_pass = (0, speech_end, "alpha beta gamma".split())
    d._pass_done.set()
    calls = []
    d._transcribe_pcm = lambda pcm: calls.append(pcm) or "SHOULD NOT BE USED"
    d._final_flush(Path(_wav_path()))
    assert calls == [], "re-transcribed the whole window to cover trailing silence"
    assert d.typed[-1] == " gamma", d.typed


def test_final_flush_transcribes_when_the_tail_holds_speech():
    """The safety side of the same check: still speaking at the key press = real work to do."""
    d = _new_daemon()
    _commit_pass(d, "alpha".split())
    _write_wav(quiet_sec=1.0, loud_sec=1.0)   # last words land after the pass, before silence
    d._anchor_byte = 0
    d._last_pass = (0, SAMPLE_RATE, "alpha".split())
    d._pass_done.set()
    _req.next_text = "alpha beta"
    d._final_flush(Path(_wav_path()))
    assert d._session_text == "alpha beta", d._session_text


def test_wav_bytes_roundtrip():
    d = _new_daemon()
    pcm = b"\x07\x00" * SAMPLE_RATE
    with wave.open(io.BytesIO(d._wav_bytes(pcm))) as r:
        assert r.getframerate() == SAMPLE_RATE
        assert r.getnchannels() == 1
        assert r.getsampwidth() == 2
        assert r.readframes(SAMPLE_RATE) == pcm


def test_translate_param_sent_only_when_enabled():
    """_post_inference adds translate=true to the form only when self.translate is on."""
    seen = {}
    orig_post = _req.post
    _req.post = lambda url, files=None, data=None, timeout=None: (
        seen.update(data or {}) or _Resp(_req.next_text))
    try:
        d = _new_daemon()
        d.translate = False
        seen.clear()
        d._post_inference(io.BytesIO(d._wav_bytes(b"\x00\x00" * 100)))
        assert "translate" not in seen, seen
        d.translate = True
        seen.clear()
        d._post_inference(io.BytesIO(d._wav_bytes(b"\x00\x00" * 100)))
        assert seen.get("translate") == "true", seen
    finally:
        _req.post = orig_post


def _wav_path():
    from dicti.daemon import TMP_WAV
    return str(TMP_WAV)


def _write_wav(loud_sec=0.0, quiet_sec=0.0):
    """A recording of `loud_sec` well above the speech RMS threshold, then `quiet_sec` of
    near-silence (the pause between your last word and the key press)."""
    with wave.open(_wav_path(), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SAMPLE_RATE)
        w.writeframes(b"\x00\x40" * int(SAMPLE_RATE * loud_sec))    # 16384 = RMS 0.5
        w.writeframes(b"\x10\x00" * int(SAMPLE_RATE * quiet_sec))   # 16 = RMS 0.0005


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"\n{len(tests)} streaming tests passed")
