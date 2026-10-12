"""
Configuration for the dicti dictation daemon.

Loads ~/.config/dicti/config.toml (TOML, stdlib tomllib) over a set of sane
defaults, so the daemon runs with no config at all. Unknown keys are ignored;
missing keys fall back to defaults.
"""

from __future__ import annotations

import logging
import os
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

log = logging.getLogger("dictation.config")


def _config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "dicti" / "config.toml"


# (stream_interval_sec, max_context_sec) per engine. Whisper medium passes average ~1.1s
# on the GPU. Parakeet does a 12s window in ~0.8s on 8 CPU threads; measured on live-paced
# Polish speech, 0.5s/12s typed words ~1-2s after they were spoken (Whisper: 8-10s) with no
# loss in accuracy, beating both 0.7s/20s and 0.3s/20s.
ENGINE_STREAM_DEFAULTS = {"whisper": (2.0, 60.0), "parakeet": (0.5, 12.0)}


@dataclass
class Config:
    # Speech-to-text engine. "parakeet" (default): Parakeet TDT v3 on CPU, fewer Polish
    # errors and 2-3x faster passes than Whisper medium, 25 European languages, detects the
    # language itself. "whisper": whisper-server, 99 languages. Translate always goes to
    # whisper-server: Parakeet cannot translate.
    engine: str = "parakeet"
    parakeet_url: str = "http://127.0.0.1:8179/inference"
    whisper_url: str = "http://127.0.0.1:8178/inference"
    language: str = "auto"  # whisper only: "auto", "en", "pl", ...
    translate: bool = False  # Whisper's built-in translate task: ANY language -> English.
    #                          One-directional (target is always English; this is a model
    #                          limit, not a setting). Runtime-toggleable via the TRANSLATE
    #                          socket command (dictate-translate); this is the startup default.

    # Dictation mode
    mode: str = "streaming"  # "streaming" (phrase-by-phrase, appears as you pause)
    #                          or "batch" (transcribe the whole utterance at STOP)

    # Streaming tuning, only used when mode == "streaming". Each pass re-transcribes the
    # whole utterance so far (full context = best quality) and appends only the words that
    # have stabilised across passes. Append-only: text behind the cursor is never rewritten.
    # Unset = the engine's default (ENGINE_STREAM_DEFAULTS): pass cost grows with the
    # window, so the faster engine gets both a shorter interval and a shorter window.
    stream_interval_sec: float | None = None  # target seconds between transcription passes
    max_context_sec: float | None = None      # cap the re-transcribed window; past this the
    #                                           text so far is committed and a fresh window starts
    stream_max_failures: int = 3         # consecutive failed passes before the session aborts
    #                                      with a visible error instead of listening silently

    # After a long (re-anchored) session, dicti re-transcribes the whole recording end to
    # end for the "perfect" full-context version behind `dictate-last` / the clipboard.
    # It runs in the background *after* the daemon is idle again, so it never delays the
    # next dictation. Set false to skip it (the streamed text is then the final one).
    refine_transcript: bool = True

    # Ignore repeats of START/STOP/TOGGLE arriving within this window. The toggle key is a
    # normal shortcut, so holding it auto-repeats and used to ping-pong the state machine.
    command_debounce_ms: int = 250

    # Session limits
    max_record_sec: int = 3600          # hard safety backstop (1 hour)
    silence_timeout_sec: int = 180      # auto-stop after this much continuous silence
    silence_check_interval_sec: float = 3.0  # how often the monitor samples the WAV tail
    silence_window_sec: float = 3.0     # length of the WAV tail analysed each sample
    silence_rms_threshold: float = 0.015  # normalised RMS (0..1) below which = silence

    # Transcript cleanup
    filter_non_speech: bool = True      # drop whisper non-speech tokens ([Silence], etc.)
    collapse_newlines: bool = True      # join whisper's per-segment newlines into spaces
    drop_hallucinations: bool = True    # drop known silence hallucinations ("the end", etc.)
    skip_silent_recordings: bool = True # skip transcription if no window exceeds speech RMS

    # Text insertion (see specs/0001-text-insertion.md)
    insert_backend: str = "auto"        # "auto" | "clipboard" | "wtype" | "ydotool" | "ibus".
    #                                     auto: wtype on wlroots Wayland, else clipboard.
    paste_keys: str = "auto"            # paste shortcut for non-ASCII: "auto" (terminals get
    #                                     ctrl+shift+v, else ctrl+v) | "ctrl+v" | "ctrl+shift+v"
    preserve_clipboard: bool = True     # restore the user's clipboard after a paste; if false,
    #                                     leave the transcript on the clipboard as a safety net
    key_delay_ms: int = 0               # inter-key delay for typing; 0 = fastest

    # Notifications. The animated panel icon already shows idle/listening/processing,
    # so per-dictation "done"/status popups are just noise (they also light the clock's
    # unread-notification dot). Default to errors only.
    #   "error" (default): only critical failures (transcription error, whisper-on-CPU)
    #   "off":             never notify
    #   "all":             also show routine status (done / empty / busy / cancelled)
    notify_level: str = "error"

    def __post_init__(self) -> None:
        if self.engine not in ENGINE_STREAM_DEFAULTS:
            log.warning("Unknown engine %r; using parakeet", self.engine)
            self.engine = "parakeet"
        interval, context = ENGINE_STREAM_DEFAULTS[self.engine]
        if self.stream_interval_sec is None:
            self.stream_interval_sec = interval
        if self.max_context_sec is None:
            self.max_context_sec = context

    @classmethod
    def load(cls) -> "Config":
        path = _config_path()
        if not path.exists():
            log.info("No config at %s; using defaults", path)
            return cls()
        try:
            with path.open("rb") as f:
                data = tomllib.load(f)
        except Exception as e:
            log.warning("Failed to read %s (%s); using defaults", path, e)
            return cls()
        known = {f.name for f in fields(cls)}
        for key in data.keys() - known:
            log.warning("Ignoring unknown config key: %s", key)
        log.info("Loaded config from %s", path)
        return cls(**{k: v for k, v in data.items() if k in known})
