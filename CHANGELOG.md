# Changelog

All notable changes to dicti are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions are date-stamped.

## [Unreleased]

### Added
- **Pluggable text-insertion backends** (`src/dicti/insert.py`), per spec 0001. Insertion is
  now chosen by capability detection, with a safe universal default and config overrides.
  - `clipboard` (default, X11 + Wayland): type ASCII via ydotool, paste non-ASCII via the
    clipboard (`xclip` on X11, `wl-clipboard` on Wayland), picking the paste shortcut from the
    focused window. **Brings Wayland (GNOME/KDE) support.**
  - `wtype` (auto-used on wlroots Wayland): native Unicode typing, no clipboard.
  - `ydotool` (ASCII-only fallback). `ibus` reserved for spec 0002.
- **Clipboard etiquette**: the user's clipboard is saved before a paste and restored at
  session end by default (`preserve_clipboard = true`); set false to leave the transcript on
  the clipboard as a re-paste safety net.
- Config: `insert_backend`, `paste_keys` (auto|ctrl+v|ctrl+shift+v), `preserve_clipboard`.
- `tests/test_insert.py` covering backend selection, ASCII/non-ASCII routing, paste-key
  modes, and clipboard save/restore.
- **"Perfect version" recovery.** At STOP the daemon now keeps the full-context
  transcription of the whole utterance (better than the live-streamed text, especially the
  first words committed with partial context) and writes it to `~/.cache/dicti/last.txt`.
  This best version is also what goes on the clipboard when `preserve_clipboard = false`.
  New `bin/dictate-last` prints it (`--copy` to put it on the clipboard).

### Changed
- Removed `paste_method` and `keep_clipboard` config keys (superseded by `insert_backend` /
  `preserve_clipboard`); old configs still load, the removed keys are ignored.
- Installer adds `wl-clipboard`; the daemon requires the right clipboard tool per session.

## [0.3.1] - 2026-06-15

### Fixed
- **Silence no longer hallucinates or runs away.** Server-side VAD is back (it had been
  removed in 0.3.0), now tuned for onset retention: `--vad-threshold 0.25`,
  `--vad-speech-pad-ms 500`, `--vad-min-speech-duration-ms 0`. On a low-output mic this
  both rejects silence (no "Thank you for watching" / random-language hallucinations, which
  could otherwise commit on sustained silence, defeat the auto-stop and run the session
  away) and keeps the first word after a pause (a tighter VAD trims quiet onsets).
- **Non-ASCII characters now insert** (Polish ąęóśżźćń, etc.) without typing them. ydotool
  1.x injects raw US-layout keycodes and silently drops off-layout characters. ASCII is
  still typed via ydotool; text containing non-ASCII is inserted byte-exact via the
  clipboard + a paste keystroke. The paste shortcut is auto-selected from the focused
  window's WM_CLASS (via `xprop`): Ctrl+Shift+V for terminals, Ctrl+V everywhere else, so it
  works in normal apps like GNOME Text Editor (which ignores Ctrl+Shift+V) as well as
  terminals. (xdotool was evaluated and rejected: its live keysym remapping to type Unicode
  deadlocked the X server.)

## [0.3.0] - 2026-06-14

Live streaming dictation that keeps batch-grade quality. Text appears as you speak,
refining with full context, instead of arriving all at once at STOP.

### Added
- **Streaming mode** (`mode = "streaming"`, now the default): the loop (`_stream_loop`)
  re-transcribes the *whole utterance so far* every `stream_interval_sec` (default 2.0s), so
  whisper always has full context (= batch quality), and types only the words that have
  **stabilised** across consecutive passes (`_common_prefix`). Append-only: it never
  backspaces or rewrites text behind the cursor, so moving focus mid-dictation can't corrupt
  a document. `max_context_sec` caps the window so a long dictation doesn't slow each pass
  without bound; `_final_flush` does one last full-context pass at STOP for the tail. The
  silence auto-stop fires after `silence_timeout_sec` with no newly committed words.
- **Silence hallucinations** are handled without VAD: a word must agree across two passes
  before it is typed, and stock silence hallucinations vary pass to pass so they never form
  a stable prefix (the `_clean_transcript` blocklist drops the fixed ones). This was chosen
  over server-side VAD, which was tried and reverted because it trims quiet speech onsets,
  eating the first word after every pause on a low-output mic.
- **Capture-live gate**: START holds the red indicator until pw-record is actually capturing
  (~50ms), so a fast speaker doesn't lose their first word into the device warm-up.
- **Batch mode kept as a fallback** (`mode = "batch"`): the v0.2 whole-utterance path is
  unchanged and one config line away.
- `tests/` directory with stdlib unit tests (`tests/test_streaming.py`): common-prefix
  stability, growing-window append-only, displayed-never-shrinks, final-flush tail, WAV
  round-trip.

### Changed
- Whisper HTTP POST factored into `_post_inference`, shared by batch (`_transcribe`, whole
  WAV file) and streaming (`_transcribe_pcm`, an in-memory WAV built from a PCM window).
- State stays `LISTENING` throughout a streaming session (typing happens live); only the
  final pass at STOP briefly shows `PROCESSING`. No tray/extension change needed.

### Notes
- Whisper transcribes one language per pass; auto-detect is most reliable with full context
  (which this design restores). Keep `language = "auto"` for mixed use, or pin it for a
  single language. A language picker in the indicator menu, plus word-level in-place
  correction (backspacing) and smart line breaks, are deferred to v0.4. See
  `docs/v0.3-streaming.md`.

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
