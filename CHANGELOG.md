# Changelog

All notable changes to dicti are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions are date-stamped.

## [0.2.1] - 2026-06-13

Polish pass after first real-world use.

### Added
- Transcript cleanup (`_clean_transcript`): drops whisper non-speech hallucinations
  (`[Silence]`, `[Foreign Language]`, `[Birds singing]`, `(silence)`, `♪…♪`) and types
  nothing when only such tokens were "heard". Config: `filter_non_speech`.
- Newline collapse: whisper's ~5s per-segment newlines are joined into spaces so text
  flows instead of stair-casing in auto-indenting editors. Config: `collapse_newlines`.
- Custom GNOME Shell extension (`gnome-extension/dicti@local`) as the top-bar indicator:
  a single icon (idle / listening-red / transcribing), left-click toggles, right-click
  menu. Installed via `install/07-install-gnome-extension.sh`.
- whisper-server now runs with `--suppress-nst` (suppresses non-speech tokens at decode).
- Silent-recording energy gate (`skip_silent_recordings`): if no window of the recording
  exceeds the speech RMS threshold, transcription is skipped entirely, so whisper can't
  hallucinate ("Thanks for watching", "The end", subtitle credits) on silence.
- Hallucination-phrase blocklist (`drop_hallucinations`): drops a segment that is wholly a
  known silence hallucination (incl. `amara.org` subtitle credits), while preserving real
  speech that merely contains those words.
- Indicator polish: lives in the centre of the top bar so it no longer jumps when GNOME's
  privacy mic indicator appears; the transcribing state is now a real animated spinner
  instead of a static three-dots icon.

### Removed
- The "empty transcript" notification popup (now just a log line).

### Changed
- The GNOME Shell extension replaces the AppIndicator indicator as the default, so other
  apps' tray icons are no longer pulled into the top bar. `indicator.py` /
  `dicti-indicator.service` remain as an optional indicator for non-GNOME desktops
  (installed but not enabled by default); the AppIndicator apt packages dropped from the
  default preflight.

### Notes
- Language auto-detect was confirmed working for Polish + English; the earlier
  "[Foreign Language]" output was a non-speech hallucination on very soft audio, now
  filtered. A language preferences pane remains a future feature.

## [0.2.0] - 2026-06-13

First public release. The project was rebuilt around the working whisper.cpp
daemon (a private prototype) and made into an MIT open-source tool.

### Added
- Silence-based auto-stop: a monitor samples the recording's RMS and ends the
  session after `silence_timeout_sec` (default 180s) of real silence.
- Universal text insertion via `ydotool type` (works in plain editors, IDEs and
  terminals); clipboard copy retained as a safety net.
- Top-bar tray indicator (`dicti-indicator`) showing idle / listening /
  transcribing, driven by a state file the daemon writes.
- Config file at `~/.config/dicti/config.toml` (timeouts, language, insertion
  method, silence thresholds), loaded via stdlib `tomllib`.
- Guided installer (`install/install.sh`) and `pyproject.toml` with console scripts.

### Changed
- Recording cap raised from a hard 60s to a 1-hour `max_record_sec` safety backstop.
- Insertion default switched from clipboard + Ctrl+Shift+V to direct typing.
- The "listening" startup notification was removed in favour of the tray indicator.

### Architecture
- whisper.cpp HTTP server (Vulkan, `ggml-medium-q5_0`), PipeWire `pw-record`,
  keyd key remap, GNOME custom shortcut → unix-socket daemon. X11/GNOME 48.
