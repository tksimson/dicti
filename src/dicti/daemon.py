#!/usr/bin/env python3
"""
dicti, local dictation daemon.

Listens on a unix socket for START / STOP / TOGGLE / CANCEL / STATUS / TRANSLATE
commands.
On START, records mic audio via pw-record. A background monitor watches the
recording for sustained silence and auto-stops after `silence_timeout_sec`;
a `max_record_sec` hard cap is the safety backstop. On STOP, the WAV is POSTed
to whisper-server and the transcript is inserted into the focused window by
typing it with ydotool (universal: no markdown-render, works in plain editors,
IDEs and terminals). The transcript is also left on the clipboard as a safety
net unless disabled.

State machine: IDLE -> LISTENING -> PROCESSING -> IDLE.
CANCEL is honored in LISTENING (aborts the recording without transcribing).
Commands that hit the wrong state are rejected with a visible notification
including elapsed PROCESSING time, so a slow transcribe never looks like a
dead key. Current state is mirrored to $XDG_RUNTIME_DIR/dictation.state on every
transition so the tray indicator can follow along.

At startup, the daemon reads the whisper-server journal for this boot and
escalates if Vulkan didn't engage, we'd rather know immediately than after
30 seconds of confusion.

Logs to journal (stdout/stderr) when run as a systemd user service.
"""

import array
import io
import logging
import math
import os
import re
import shutil
import signal
import socket
import subprocess
import threading
import time
import wave
from pathlib import Path

import requests

from dicti.config import Config
from dicti.insert import make_inserter

_XDG = os.environ.get("XDG_RUNTIME_DIR")
if not _XDG:
    raise SystemExit("XDG_RUNTIME_DIR not set, daemon must run inside a logind user session")

SOCK_PATH = Path(_XDG) / "dictation.sock"
STATE_PATH = Path(_XDG) / "dictation.state"
TRANSLATE_PATH = Path(_XDG) / "dictation.translate"  # "ON"/"OFF", watched by the indicators
TMP_WAV = Path("/tmp/dictation-record.wav")

SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2  # s16 mono
WAV_HEADER_BYTES = 44

# A segment that is wholly a non-speech annotation, e.g. "[Silence]", "[ Foreign
# Language ]", "(silence)", "[Birds singing]", "♪ music ♪".
_NON_SPEECH_SEGMENT_RE = re.compile(r"^\s*[\[(*♪].*[\])*♪]\s*$")
# A short inline non-speech token; kept short so real parenthetical speech survives.
_INLINE_NON_SPEECH_RE = re.compile(
    r"\s*(?:[\[(][^\[\]()]{0,40}[\])]|[♪*][^♪*\n]{0,40}[♪*])\s*"
)

# Whisper hallucinates these on silent/low-energy audio (trained on YouTube etc.).
# Only dropped when a whole segment IS one of them, distinctive enough not to be
# real dictation. "amara.org" subtitle credits are matched as a substring.
_HALLUCINATION_PHRASES = {
    "thanks for watching", "thanks for watching everyone", "thanks for watching this video",
    "thank you for watching", "thank you for watching this video",
    "the end", "please subscribe", "subscribe", "like and subscribe",
    "please like and subscribe", "subscribe to my channel",
    "see you in the next video", "see you next time", "see you next video",
    "dziękuję za uwagę", "dziękuję za obejrzenie",
    "napisy stworzone przez społeczność amara.org",
}


def _normalize_phrase(s: str) -> str:
    s = re.sub(r"^[^\w]+|[^\w]+$", "", s.strip().lower())
    return re.sub(r"\s+", " ", s)


def _is_hallucination(normalized: str) -> bool:
    return normalized in _HALLUCINATION_PHRASES or "amara.org" in normalized


def _common_prefix(a: list[str], b: list[str]) -> list[str]:
    """Longest leading run of words shared by two word lists. Used to find the text that
    has stabilised across two consecutive re-transcription passes (safe to commit)."""
    out = []
    for x, y in zip(a, b):
        if x != y:
            break
        out.append(x)
    return out

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("dictation")


class State:
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"


class Daemon:
    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or Config.load()
        # Whisper translate task (-> English). Mutable at runtime via the TRANSLATE
        # command; seeded from config so a user can default it on.
        self.translate = bool(self.cfg.translate)
        self.state = State.IDLE
        self.lock = threading.Lock()
        self.recorder: subprocess.Popen | None = None
        self.timeout_timer: threading.Timer | None = None
        self.silence_thread: threading.Thread | None = None
        self.silence_stop = threading.Event()
        self.processing_started_at: float | None = None
        # Streaming session state (mode == "streaming"). Guarded by _flush_lock so
        # phrase flushes and the final stop flush never overlap or double-type.
        self._flush_lock = threading.Lock()
        self._anchor_byte = 0          # start of the current re-transcribed context window
        self._displayed_words: list[str] = []  # words already typed this window
        self._typed_any = False        # have we typed anything this session?
        self._session_text = ""        # full text typed this session (for clipboard)
        self._last_progress = 0.0      # monotonic time of last committed word (auto-stop)
        self.inserter = make_inserter(self.cfg)
        log.info("Insertion backend: %s (session=%s)", self.inserter.name,
                 os.environ.get("XDG_SESSION_TYPE", "?"))
        self._write_state()
        self._write_translate()

    # ---- state -------------------------------------------------------------

    def _set_state(self, state: str) -> None:
        """Assign state and mirror it to the state file. Caller holds self.lock."""
        self.state = state
        self._write_state()

    def _write_state(self) -> None:
        try:
            STATE_PATH.write_text(self.state + "\n")
        except Exception as e:
            log.warning("Could not write state file %s: %s", STATE_PATH, e)

    def _write_translate(self) -> None:
        # Mirror the translate flag so the indicators can show the toggle's real state
        # (survives an external `dictate-translate` or a config-set startup default).
        try:
            TRANSLATE_PATH.write_text(("ON" if self.translate else "OFF") + "\n")
        except Exception as e:
            log.warning("Could not write translate file %s: %s", TRANSLATE_PATH, e)

    # ---- notifications -----------------------------------------------------

    def notify(self, summary: str, body: str = "",
               urgency: str = "low", timeout_ms: int = 2000) -> None:
        # Gate by notify_level. Routine status (low/normal) is suppressed unless
        # "all"; only "critical" survives at the default "error" level (the panel
        # icon conveys normal state, so routine popups are pure noise).
        level = getattr(self.cfg, "notify_level", "error")
        if level == "off":
            return
        if level == "error" and urgency != "critical":
            return
        try:
            subprocess.run(
                ["notify-send", "-u", urgency, "-t", str(timeout_ms),
                 "-a", "dictation", summary, body],
                check=False,
                timeout=2,
            )
        except Exception as e:
            log.warning("notify-send failed: %s", e)

    def _processing_elapsed(self) -> int:
        started = self.processing_started_at
        return int(time.monotonic() - started) if started else 0

    def _notify_busy(self) -> None:
        self.notify(
            "Dictation busy",
            f"Still transcribing… {self._processing_elapsed()}s elapsed",
            urgency="normal",
            timeout_ms=3000,
        )

    # ---- recording lifecycle ----------------------------------------------

    def _abort_recorder_unlocked(self) -> None:
        """Stop pw-record, the safety timer and the silence monitor.
        Caller must hold self.lock."""
        if self.timeout_timer:
            self.timeout_timer.cancel()
            self.timeout_timer = None
        self.silence_stop.set()
        if self.recorder and self.recorder.poll() is None:
            self.recorder.send_signal(signal.SIGINT)
            try:
                self.recorder.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.recorder.kill()
        self.recorder = None

    def start_recording(self) -> None:
        with self.lock:
            if self.state == State.PROCESSING:
                log.info("START rejected; state=PROCESSING")
                self._notify_busy()
                return
            if self.state != State.IDLE:
                log.info("START rejected; state=%s", self.state)
                self.notify("Dictation busy", f"state={self.state}", urgency="normal")
                return
            TMP_WAV.unlink(missing_ok=True)
            log.info("Starting pw-record -> %s", TMP_WAV)
            self.recorder = subprocess.Popen(
                ["pw-record", "--rate=16000", "--format=s16", "--channels=1", str(TMP_WAV)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Hold IDLE until capture is actually live, so the red indicator never precedes
            # real recording (otherwise a fast speaker loses their first word). ~50ms typ.
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                if self._data_end() > 1000:
                    break
                time.sleep(0.01)
            self._set_state(State.LISTENING)
            self.timeout_timer = threading.Timer(self.cfg.max_record_sec, self._safety_stop)
            self.timeout_timer.daemon = True
            self.timeout_timer.start()
            self.silence_stop.clear()
            if self.cfg.mode == "streaming":
                self._anchor_byte = 0
                self._displayed_words = []
                self._typed_any = False
                self._session_text = ""
                monitor = self._stream_loop
            else:
                monitor = self._monitor_silence
            self.silence_thread = threading.Thread(target=monitor, daemon=True)
            self.silence_thread.start()
        # No "listening" popup by design, the tray indicator shows the state.
        log.info("Listening (mode=%s, max %ds, auto-stop after %ds silence)",
                 self.cfg.mode, self.cfg.max_record_sec, self.cfg.silence_timeout_sec)

    def _safety_stop(self) -> None:
        log.info("Safety timeout fired (%ds)", self.cfg.max_record_sec)
        self.stop_and_transcribe()

    def _monitor_silence(self) -> None:
        """Auto-stop after sustained silence. Reads the tail of the growing WAV
        and computes RMS; pw-record's header frame-count is unreliable mid-record,
        so we read raw bytes from the file tail directly."""
        interval = self.cfg.silence_check_interval_sec
        window_bytes = int(self.cfg.silence_window_sec * SAMPLE_RATE) * BYTES_PER_SAMPLE
        silent_seconds = 0.0
        while not self.silence_stop.wait(interval):
            rms = self._tail_rms(window_bytes)
            if rms is None:
                continue
            if rms < self.cfg.silence_rms_threshold:
                silent_seconds += interval
                if silent_seconds >= self.cfg.silence_timeout_sec:
                    log.info("Silence auto-stop (%.0fs quiet, rms=%.4f)", silent_seconds, rms)
                    self.stop_and_transcribe()
                    return
            else:
                silent_seconds = 0.0

    def _tail_rms(self, window_bytes: int) -> float | None:
        try:
            size = TMP_WAV.stat().st_size
        except OSError:
            return None
        data_bytes = size - WAV_HEADER_BYTES
        if data_bytes <= 0:
            return None
        read_len = min(window_bytes, data_bytes)
        read_len -= read_len % BYTES_PER_SAMPLE  # keep int16-aligned
        if read_len <= 0:
            return None
        try:
            with TMP_WAV.open("rb") as f:
                f.seek(size - read_len)
                raw = f.read(read_len)
        except OSError:
            return None
        if len(raw) < BYTES_PER_SAMPLE:
            return None
        samples = array.array("h")  # signed 16-bit, native order (== little-endian on x86)
        samples.frombytes(raw)
        if not samples:
            return None
        mean_sq = sum(s * s for s in samples) / len(samples)
        return math.sqrt(mean_sq) / 32768.0

    # ---- streaming -------------------------------------------------------

    def _data_end(self) -> int:
        """Bytes of PCM data currently in TMP_WAV (file size minus header)."""
        try:
            return max(0, TMP_WAV.stat().st_size - WAV_HEADER_BYTES)
        except OSError:
            return 0

    def _stream_loop(self) -> None:
        """Streaming monitor (mode == "streaming"). Each pass re-transcribes the WHOLE
        utterance so far (from the current anchor to now), so whisper always has full
        context = batch-grade quality, and appends only the words that have *stabilised*
        (agree with the previous pass). Append-only: text behind the cursor is never
        rewritten, so it can't be corrupted if focus moves.

        No server-side VAD: VAD trims quiet speech onsets, eating the first word after a
        pause. Instead, the stabilise-across-passes rule rejects silence hallucinations
        (they vary pass to pass, so never form a stable prefix) and the `_clean_transcript`
        blocklist drops the stock ones, while every real onset reaches whisper intact.

        When the window grows past max_context_sec the text so far is committed wholesale
        and a fresh context window starts, to bound the per-pass cost. The session
        auto-stops after silence_timeout_sec with no newly committed words."""
        max_ctx_bytes = int(self.cfg.max_context_sec * SAMPLE_RATE) * BYTES_PER_SAMPLE
        min_window = SAMPLE_RATE * BYTES_PER_SAMPLE // 2  # need ~0.5s before a first pass
        prev_words: list[str] = []
        self._last_progress = time.monotonic()
        while not self.silence_stop.is_set():
            t0 = time.monotonic()
            anchor = self._anchor_byte
            end = self._data_end()
            if end - anchor >= min_window:
                pcm = self._read_pcm(anchor, end)
                words = self._clean_transcript(self._transcribe_pcm(pcm)).split()
                if self.silence_stop.is_set():
                    return  # a STOP raced in; let the final flush be authoritative
                with self._flush_lock:
                    if end - anchor >= max_ctx_bytes:
                        # window full: commit everything and re-anchor for bounded cost
                        self._emit_words(words[len(self._displayed_words):])
                        self._anchor_byte = end
                        self._displayed_words = []
                        prev_words = []
                    else:
                        stable = _common_prefix(words, prev_words)
                        if len(stable) > len(self._displayed_words):
                            self._emit_words(stable[len(self._displayed_words):])
                            self._displayed_words = stable
                        prev_words = words
            if time.monotonic() - self._last_progress >= self.cfg.silence_timeout_sec:
                log.info("Silence auto-stop (%ds without new committed words)",
                         self.cfg.silence_timeout_sec)
                self.stop_and_transcribe()
                return
            wait = self.cfg.stream_interval_sec - (time.monotonic() - t0)
            if self.silence_stop.wait(max(0.1, wait)):
                return

    def _emit_words(self, new_words: list[str]) -> None:
        """Insert a list of newly-stable words, append-only, space-joined. Caller holds
        _flush_lock. Reconstructs spacing; clipboard etiquette is handled at session end."""
        if not new_words:
            return
        piece = (" " if self._typed_any else "") + " ".join(new_words)
        self.inserter.insert(piece)
        self._typed_any = True
        self._session_text += piece
        self._last_progress = time.monotonic()  # commit progress, drives silence auto-stop

    def _final_flush(self) -> str:
        """At STOP: re-transcribe the final context window once more (full context = best
        quality) and type whatever the stream loop hadn't committed yet (the tail). Returns
        the full-window transcription text."""
        pcm = self._read_pcm(self._anchor_byte, self._data_end())
        words = self._clean_transcript(self._transcribe_pcm(pcm)).split() if pcm else []
        with self._flush_lock:
            if len(words) > len(self._displayed_words):
                self._emit_words(words[len(self._displayed_words):])
                self._displayed_words = words
        return " ".join(words)

    def _best_transcript(self, final_text: str) -> str:
        """The full-context "perfect" transcription of the whole utterance. For a session
        that never re-anchored, _final_flush already produced it; a long (re-anchored) one is
        re-transcribed end to end. Better than the live-typed text, especially the first
        words, which streaming had to commit with only partial context."""
        if self._anchor_byte == 0:
            return final_text or self._session_text
        full = self._read_pcm(0, self._data_end())
        best = self._clean_transcript(self._transcribe_pcm(full)) if full else ""
        return best or final_text or self._session_text

    def _save_last_transcript(self, text: str) -> None:
        """Write the best transcript to a file so the perfect version is recoverable even
        when the clipboard is preserved (see preserve_clipboard)."""
        if not text:
            return
        try:
            path = Path.home() / ".cache" / "dicti" / "last.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text + "\n")
            log.info("Saved transcript (%d chars) to %s", len(text), path)
        except Exception as e:
            log.warning("Could not save transcript: %s", e)

    def _read_pcm(self, start: int, end: int) -> bytes:
        """Read raw PCM bytes [start:end] (offsets into the data, header excluded)."""
        end -= (end - start) % BYTES_PER_SAMPLE  # keep int16-aligned
        if end <= start:
            return b""
        try:
            with TMP_WAV.open("rb") as f:
                f.seek(WAV_HEADER_BYTES + start)
                return f.read(end - start)
        except OSError:
            return b""

    def _wav_bytes(self, pcm: bytes) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(BYTES_PER_SAMPLE)
            w.setframerate(SAMPLE_RATE)
            w.writeframes(pcm)
        return buf.getvalue()

    def stop_and_transcribe(self) -> None:
        with self.lock:
            if self.state == State.PROCESSING:
                log.info("STOP rejected; state=PROCESSING")
                self._notify_busy()
                return
            if self.state != State.LISTENING:
                log.info("STOP rejected; state=%s", self.state)
                return
            self._set_state(State.PROCESSING)
            self.processing_started_at = time.monotonic()
            streaming = self.cfg.mode == "streaming"
            self._abort_recorder_unlocked()

        try:
            if streaming:
                final_text = self._final_flush()
                best = self._best_transcript(final_text)
                self._save_last_transcript(best)
                # The perfect (full-context) text goes to the clipboard, so preserve=false
                # leaves the best version, not the streamed one, as the re-paste fallback.
                self.inserter.end_session(best, self.cfg.preserve_clipboard)
                if self._typed_any or best:
                    self.notify("done", best[:80], urgency="low")
                else:
                    self.notify("empty transcript", "", urgency="normal")
            else:
                text = self._clean_transcript(self._transcribe())
                if text:
                    self.inserter.insert(text)
                    self.inserter.end_session(text, self.cfg.preserve_clipboard)
                    self.notify("done", text[:80], urgency="low")
                else:
                    self.notify("empty transcript", "", urgency="normal")
        except Exception as e:
            log.exception("Transcribe/insert failed")
            self.notify("dictation error", str(e)[:80], urgency="critical")
        finally:
            with self.lock:
                self._set_state(State.IDLE)
                self.processing_started_at = None

    def cancel(self) -> None:
        with self.lock:
            if self.state == State.LISTENING:
                self._abort_recorder_unlocked()
                TMP_WAV.unlink(missing_ok=True)
                self._set_state(State.IDLE)
                log.info("Cancelled listening")
                notify_args = ("cancelled", "", "normal")
            elif self.state == State.PROCESSING:
                log.info("CANCEL during PROCESSING (no-op)")
                notify_args = (
                    "Cannot cancel",
                    f"transcription in progress ({self._processing_elapsed()}s)",
                    "normal",
                )
            else:
                log.info("CANCEL with no recording in progress")
                notify_args = ("Nothing to cancel", "", "low")
        self.notify(*notify_args)

    # ---- transcription + insertion ----------------------------------------

    def _clean_transcript(self, text: str) -> str:
        """Strip whisper's non-speech hallucinations and flatten segment newlines.

        Whisper annotates low-energy/ambiguous audio with bracketed tokens such as
        "[Silence]", "[ Foreign Language ]", "(silence)", "[Birds singing]", "♪ … ♪".
        It also emits one ~5s segment per line, which stair-cases in auto-indenting
        editors. We drop whole-segment annotations, strip short inline ones, and join
        segments with spaces (configurable)."""
        if not text:
            return ""
        joiner = " " if self.cfg.collapse_newlines else "\n"
        cleaned = []
        for seg in text.split("\n"):
            s = seg.strip()
            if not s:
                continue
            if self.cfg.filter_non_speech:
                if _NON_SPEECH_SEGMENT_RE.match(s):
                    continue
                s = _INLINE_NON_SPEECH_RE.sub(" ", s).strip()
                if not s:
                    continue
            if self.cfg.drop_hallucinations and _is_hallucination(_normalize_phrase(s)):
                continue
            cleaned.append(s)
        result = joiner.join(cleaned)
        return re.sub(r"[ \t]{2,}", " ", result).strip()

    def _has_speech(self) -> bool:
        """True if any window of the recording exceeds the speech RMS threshold.
        Used to skip transcription of silent recordings, where whisper otherwise
        hallucinates ("Thanks for watching", "The end", …). Downsamples within each
        window for speed and returns early on the first speech window."""
        try:
            size = TMP_WAV.stat().st_size
        except OSError:
            return True  # don't block on error
        window = int(self.cfg.silence_window_sec * SAMPLE_RATE) * BYTES_PER_SAMPLE
        if window <= 0:
            return True
        thr = self.cfg.silence_rms_threshold
        pos = WAV_HEADER_BYTES
        try:
            with TMP_WAV.open("rb") as f:
                while pos < size:
                    f.seek(pos)
                    raw = f.read(window)
                    pos += window
                    n = len(raw) - (len(raw) % BYTES_PER_SAMPLE)
                    if n < BYTES_PER_SAMPLE:
                        continue
                    samples = array.array("h")
                    samples.frombytes(raw[:n])
                    sub = samples[::8]  # energy gate tolerates downsampling
                    if not sub:
                        continue
                    rms = math.sqrt(sum(s * s for s in sub) / len(sub)) / 32768.0
                    if rms >= thr:
                        return True
        except OSError:
            return True
        return False

    def _transcribe(self) -> str:
        if not TMP_WAV.exists() or TMP_WAV.stat().st_size < 2000:
            log.warning("Recording too small or missing: %s", TMP_WAV)
            return ""
        if self.cfg.skip_silent_recordings and not self._has_speech():
            log.info("No speech above threshold; skipping transcription (silent recording)")
            return ""
        with TMP_WAV.open("rb") as f:
            return self._post_inference(f)

    def _transcribe_pcm(self, pcm: bytes) -> str:
        """Transcribe a raw PCM buffer (streaming segment) by wrapping it in a WAV."""
        return self._post_inference(io.BytesIO(self._wav_bytes(pcm)))

    def _post_inference(self, fileobj) -> str:
        t0 = time.monotonic()
        data = {"language": self.cfg.language, "response_format": "json"}
        if self.translate:
            # whisper-server flips into Whisper's translate task: source audio -> English,
            # regardless of spoken language. Only English output is possible (model limit).
            data["translate"] = "true"
        r = requests.post(
            self.cfg.whisper_url,
            files={"file": ("audio.wav", fileobj, "audio/wav")},
            data=data,
            timeout=120,
        )
        r.raise_for_status()
        elapsed = time.monotonic() - t0
        text = (r.json().get("text") or "").strip()
        log.info("Inference %.2fs -> %d chars: %r", elapsed, len(text), text[:120])
        return text

    # ---- startup checks ----------------------------------------------------

    def check_whisper_backend(self) -> None:
        """Read whisper-server journal once at startup. Warn loudly on CPU fallback."""
        try:
            out = subprocess.run(
                ["journalctl", "--user", "-u", "whisper-server", "-b", "--no-pager"],
                capture_output=True, text=True, timeout=5,
            ).stdout
        except Exception as e:
            log.warning("Could not check whisper-server backend: %s", e)
            return
        if "ggml_vulkan: Found" in out and "using Vulkan0 backend" in out:
            log.info("whisper-server backend OK: Vulkan engaged")
        elif "no GPU found" in out or "No devices found" in out:
            log.error(
                "whisper-server fell back to CPU, inference will be 4-5x slower. "
                "Fix: `systemctl --user restart whisper-server` "
                "(graphical session must be up)"
            )
            self.notify(
                "Dictation degraded",
                "whisper running on CPU - see journalctl --user -u whisper-server",
                urgency="critical",
                timeout_ms=8000,
            )
        else:
            log.warning("whisper-server backend status unknown, no Vulkan/GPU markers in journal")

    # ---- socket server -----------------------------------------------------

    def serve(self) -> None:
        SOCK_PATH.unlink(missing_ok=True)
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(str(SOCK_PATH))
        os.chmod(SOCK_PATH, 0o600)
        srv.listen(4)
        log.info("Listening on %s", SOCK_PATH)
        self.check_whisper_backend()
        while True:
            conn, _ = srv.accept()
            try:
                cmd = conn.recv(64).decode("utf-8", "replace").strip().upper()
                log.info("Got command: %s (state=%s)", cmd, self.state)
                if cmd == "START":
                    threading.Thread(target=self.start_recording, daemon=True).start()
                elif cmd == "STOP":
                    threading.Thread(target=self.stop_and_transcribe, daemon=True).start()
                elif cmd == "TOGGLE":
                    target = self.start_recording if self.state == State.IDLE else self.stop_and_transcribe
                    threading.Thread(target=target, daemon=True).start()
                elif cmd == "CANCEL":
                    threading.Thread(target=self.cancel, daemon=True).start()
                elif cmd == "STATUS":
                    conn.send(self.state.encode())
                elif cmd == "TRANSLATE":
                    self.translate = not self.translate
                    self._write_translate()
                    new = "ON" if self.translate else "OFF"
                    log.info("Translate-to-English: %s", new)
                    self.notify(
                        f"Translate -> English: {new}",
                        "Speech is transcribed to English." if self.translate
                        else "Speech is transcribed in its own language.",
                        urgency="normal",
                    )
                    conn.send(new.encode())
                else:
                    log.warning("Unknown command: %r", cmd)
            finally:
                conn.close()


def preflight() -> None:
    for bin_ in ("pw-record", "ydotool", "notify-send", "journalctl"):
        if not shutil.which(bin_):
            raise SystemExit(f"Missing required binary: {bin_}")
    # Clipboard tool for inserting non-ASCII text: wl-clipboard on Wayland, xclip on X11.
    from dicti import insert
    clip = "wl-copy" if insert.is_wayland() else "xclip"
    if not shutil.which(clip):
        log.warning("Clipboard tool %s not found: non-ASCII text (e.g. Polish) won't insert. "
                    "Install it (%s).", clip,
                    "wl-clipboard" if clip == "wl-copy" else "xclip")
    if not SOCK_PATH.parent.exists():
        raise SystemExit(f"XDG_RUNTIME_DIR missing: {SOCK_PATH.parent}")


def main() -> None:
    preflight()
    Daemon().serve()


if __name__ == "__main__":
    main()
