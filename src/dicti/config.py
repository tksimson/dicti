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


@dataclass
class Config:
    # Whisper backend
    whisper_url: str = "http://127.0.0.1:8178/inference"
    language: str = "auto"  # "auto", "en", "pl", ...

    # Dictation mode
    mode: str = "streaming"  # "streaming" (phrase-by-phrase, appears as you pause)
    #                          or "batch" (transcribe the whole utterance at STOP)

    # Streaming tuning, only used when mode == "streaming". Each pass re-transcribes the
    # whole utterance so far (full context = best quality) and appends only the words that
    # have stabilised across passes. Append-only: text behind the cursor is never rewritten.
    stream_interval_sec: float = 2.0     # target seconds between transcription passes
    max_context_sec: float = 60.0        # cap the re-transcribed window; past this the text
    #                                      so far is committed and a fresh context window starts

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

    @classmethod
    def load(cls) -> "Config":
        path = _config_path()
        cfg = cls()
        if not path.exists():
            log.info("No config at %s; using defaults", path)
            return cfg
        try:
            with path.open("rb") as f:
                data = tomllib.load(f)
        except Exception as e:
            log.warning("Failed to read %s (%s); using defaults", path, e)
            return cfg
        known = {f.name for f in fields(cls)}
        for key, value in data.items():
            if key in known:
                setattr(cfg, key, value)
            else:
                log.warning("Ignoring unknown config key: %s", key)
        log.info("Loaded config from %s", path)
        return cfg
