#!/usr/bin/env python3
"""Unit tests for the v0.3.8 reliability fixes.

Two field failures drove these: dicti kept "processing" long after the last word was typed,
and it could go quiet, accepting keypresses while doing nothing. Covered here:

  - PROCESSING ends as soon as the text is typed; full-context refinement runs in background
  - a refine job stands down when a new dictation starts (whisper-server is single-threaded)
  - a failing streaming pass never kills the loop, and repeated failures end the session
  - a recorder that dies is detected instead of listening against a WAV that never grows
  - a held-down toggle key is debounced instead of ping-ponging the state machine
  - busy/rejection notifications survive the default notify_level="error"

Pure stdlib; stubs `requests` and the inserter. Run with: python3 tests/test_reliability.py
"""

import os
import sys
import tempfile
import threading
import time
import types
import wave

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

_tmp = tempfile.mkdtemp()
os.environ["XDG_RUNTIME_DIR"] = _tmp
os.environ["XDG_CONFIG_HOME"] = _tmp
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dicti.daemon import Daemon, State, SAMPLE_RATE, TMP_WAV  # noqa: E402
from dicti.config import Config  # noqa: E402


class _FakeInserter:
    name = "fake"

    def __init__(self):
        self.typed = []
        self.ended = []

    def insert(self, text):
        self.typed.append(text)

    def end_session(self, transcript, preserve_clipboard):
        self.ended.append((transcript, preserve_clipboard))


def _new_daemon(**cfgkw):
    cfg = Config()
    cfg.mode = "streaming"
    for k, v in cfgkw.items():
        setattr(cfg, k, v)
    d = Daemon(cfg)
    d.inserter = _FakeInserter()
    d.notes = []
    d.notify = lambda s, b="", urgency="low", timeout_ms=2000, important=False: (
        d.notes.append((s, urgency, important)))
    d.saved = []                                  # keep the user's real last.txt untouched
    d._save_last_transcript = d.saved.append
    return d


def _write_wav(seconds=1.0):
    with wave.open(str(TMP_WAV), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SAMPLE_RATE)
        w.writeframes(b"\x10\x00" * int(SAMPLE_RATE * seconds))


# --- issue 1: PROCESSING must end when the typing does ------------------------

def test_stop_returns_to_idle_before_refine_finishes():
    """The slow full-context pass must not hold the state machine in PROCESSING."""
    d = _new_daemon()
    _write_wav(2.0)
    d.state = State.LISTENING
    d._anchor_byte = 100          # re-anchored session -> refinement is warranted
    d._session_text = "streamed text"
    d._last_pass = (100, d._data_end(), "streamed text".split())
    d._pass_done.set()

    release = threading.Event()
    started = threading.Event()

    def slow_full_pass(pcm):
        started.set()
        release.wait(5)
        return "refined text"

    d._transcribe_pcm = slow_full_pass
    t0 = time.monotonic()
    d.stop_and_transcribe()
    elapsed = time.monotonic() - t0

    assert d.state == State.IDLE, d.state
    assert elapsed < 1.0, f"stop blocked {elapsed:.1f}s on background work"
    assert d.saved == ["streamed text"], d.saved   # streamed text is saved immediately
    assert started.wait(2), "refine never ran"
    release.set()
    for _ in range(50):                            # ... and upgraded when refinement lands
        if d.saved[-1] == "refined text":
            break
        time.sleep(0.05)
    assert d.saved[-1] == "refined text", d.saved


def test_refine_stands_down_when_a_new_session_starts():
    """whisper-server is single-threaded: stale refinement must not delay live dictation."""
    d = _new_daemon()
    _write_wav(1.0)
    path = TMP_WAV
    calls = []
    d._transcribe_pcm = lambda pcm: calls.append(pcm) or "refined"
    d._session_seq = 7
    d._refine(path, 6, "streamed", True)   # seq 6 is stale vs the daemon's 7
    assert calls == [], "a superseded refine still hit whisper-server"


def test_no_refine_for_a_short_session():
    """Never re-anchored: the final flush already had full context, so there is nothing
    to refine and nothing to wait for."""
    d = _new_daemon()
    _write_wav(1.0)
    d.state = State.LISTENING
    d._anchor_byte = 0
    d._last_pass = (0, d._data_end(), ["hello"])
    d._pass_done.set()
    calls = []
    d._transcribe_pcm = lambda pcm: calls.append(pcm) or "hello"
    d.stop_and_transcribe()
    assert calls == [], "short session paid for an extra full-context pass"
    assert d.state == State.IDLE


# --- issue 2: the daemon must never go quietly dead ---------------------------

def test_stream_loop_survives_a_failing_pass():
    d = _new_daemon(stream_interval_sec=0.01, stream_max_failures=3)
    _write_wav(1.0)
    calls = []

    def flaky(pcm):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("connection reset")
        d.silence_stop.set()
        return "recovered"

    d._transcribe_pcm = flaky
    d._stream_loop()
    assert len(calls) == 2, f"loop died on the first failure ({calls})"


def test_stream_loop_aborts_visibly_after_repeated_failures():
    d = _new_daemon(stream_interval_sec=0.01, stream_max_failures=2)
    _write_wav(1.0)
    d.state = State.LISTENING
    stops = []
    d.stop_and_transcribe = lambda: stops.append(1)

    def always_fails(pcm):
        raise RuntimeError("whisper-server is down")

    d._transcribe_pcm = always_fails
    d._stream_loop()
    assert stops == [1], "session kept listening after whisper-server gave up"
    assert any(u == "critical" for _, u, _ in d.notes), d.notes


def test_monitor_crash_cannot_strand_the_session():
    d = _new_daemon()
    d.state = State.LISTENING
    stops = []
    d.stop_and_transcribe = lambda: stops.append(1)
    d._run_monitor(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert stops == [1], "a crashed monitor left the session in LISTENING"
    assert any(u == "critical" for _, u, _ in d.notes), d.notes


def test_dead_recorder_is_detected():
    class _Dead:
        returncode = 1

        def poll(self):
            return 1

    d = _new_daemon(stream_interval_sec=0.01)
    d.recorder = _Dead()
    d.silence_stop.clear()
    stops = []
    d.stop_and_transcribe = lambda: stops.append(1)
    d._stream_loop()
    assert stops == [1], "a dead pw-record went unnoticed"


def test_normal_stop_is_not_reported_as_a_dead_recorder():
    class _Killed:
        def poll(self):
            return -2  # SIGINT from our own stop

    d = _new_daemon()
    d.recorder = _Killed()
    d.silence_stop.set()          # a stop is in progress
    assert not d._recorder_died()


# --- key repeat ---------------------------------------------------------------

def test_repeat_commands_are_debounced():
    d = _new_daemon(command_debounce_ms=250)
    assert not d._debounced("TOGGLE")     # first press is accepted
    assert d._debounced("TOGGLE")         # auto-repeat within the window is dropped
    assert d._debounced("TOGGLE")
    d._last_cmd_at -= 1.0                 # simulate the window elapsing
    assert not d._debounced("TOGGLE")


def test_toggle_decides_under_the_lock():
    """A TOGGLE arriving while the daemon is LISTENING must stop, never re-START."""
    d = _new_daemon()
    d.state = State.LISTENING
    seen = []
    d.start_recording = lambda: seen.append("start")
    d.stop_and_transcribe = lambda: seen.append("stop")
    d.toggle()
    assert seen == ["stop"], seen


# --- feedback -----------------------------------------------------------------

def test_busy_notification_survives_default_notify_level():
    """notify_level="error" (the default) used to swallow every busy popup, so a rejected
    keypress produced no text, no popup, and no explanation."""
    cfg = Config()
    cfg.notify_level = "error"
    d = Daemon(cfg)
    sent = []
    import dicti.daemon as dd
    orig = dd.subprocess.run
    dd.subprocess.run = lambda *a, **k: sent.append(a[0]) or types.SimpleNamespace()
    try:
        d.notify("routine", "", urgency="normal")
        assert sent == [], "routine status leaked at notify_level=error"
        d.notify("Dictation busy", "", urgency="normal", important=True)
        assert len(sent) == 1, "direct feedback on a keypress was silently dropped"
        cfg.notify_level = "off"
        d.notify("Dictation busy", "", urgency="normal", important=True)
        assert len(sent) == 1, "notify_level=off must stay silent"
    finally:
        dd.subprocess.run = orig


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"\n{len(tests)} reliability tests passed")
