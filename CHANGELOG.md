# Changelog

All notable changes to dicti are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions are date-stamped.

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
