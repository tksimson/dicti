# Changelog

All notable changes to dicti are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions are date-stamped.

## [0.3.8] - 2026-08-03

Reliability release. Two things made dicti feel unreliable in daily use: it kept
"processing" long after the last word was on screen, and it could go quiet, accepting
keypresses while doing nothing. Both are fixed at the root.

### Fixed
- **Dictation ends when the typing does.** Stopping used to re-transcribe the *entire*
  recording end to end before releasing the state machine, purely to fill the clipboard and
  `dictate-last`. On a few minutes of audio that was 12s+ of "still transcribing" with
  everything already typed, and it grew with session length. That full-context refinement now
  runs in the background after the daemon is idle again, and only for long (re-anchored)
  sessions where it actually improves on the streamed text. Disable it with
  `refine_transcript = false`.
- **No redundant inference at stop.** Almost always there is nothing left to transcribe: you
  stop talking, then reach for the key, so the only audio the last streaming pass missed is
  your own silence. dicti used to re-run the whole context window over it and return the
  identical words, 4s+ of PROCESSING for nothing. The final flush now reuses that pass
  whenever the audio after it holds no speech, and only pays for an inference when you really
  were still speaking. (The check is biased towards "speech": a wrong silent verdict would
  drop your last words, a wrong speech verdict just costs what it used to.) It also lets a
  pass that is already in flight land rather than queueing a second one behind it.
- **A held toggle key no longer ping-pongs the state machine.** The shortcut is an ordinary
  key, so holding it auto-repeats; a burst used to start/stop/start within a second and could
  leave dicti recording when it looked idle. Repeats within `command_debounce_ms` (250ms) are
  ignored, and TOGGLE now decides start-vs-stop under the lock instead of on a stale read.
- **A failing transcription pass no longer kills the session silently.** Any error in the
  streaming loop (whisper-server restarting, a dropped connection, ydotoold down) used to end
  the monitor thread without a word: dicti kept recording, typed nothing and reported nothing
  until the one-hour cap. Passes now retry, and after `stream_max_failures` (3) the session
  ends with a visible error.
- **A dead recorder is detected.** If `pw-record` exits (device grabbed, PipeWire restart),
  the session stops with an error instead of listening to a file that never grows.
- **Rejected keypresses are visible again.** `notify_level = "error"` (the default since
  0.3.5) was swallowing every "busy" popup, so a keypress that arrived mid-transcription
  produced no text, no popup and no explanation. Direct feedback on your own keypress now
  survives that level; `notify_level = "off"` still silences everything.
- **A stalled client can no longer wedge the daemon.** The socket accept loop is
  single-threaded and had no read timeout, so one connection that never sent a command froze
  every subsequent keypress until a restart.

### Added
- Config: `refine_transcript` (default true), `command_debounce_ms` (default 250),
  `stream_max_failures` (default 3).
- 11 reliability tests (`tests/test_reliability.py`) plus silent-tail cases in
  `tests/test_streaming.py`, covering each failure above.

## [0.3.7] - 2026-06-29

### Added
- **Translate to English.** Speak any language, type English, using Whisper's own built-in
  translate task. No new model, no new dependency: the medium model already ships with it.
  Off by default; set `translate = true` in config, or toggle it live with the new
  `dictate-translate` command (bindable to a key) or the **Translate to English** switch in
  the indicator menu. One-directional by design: the target is always English (a Whisper
  model limit; reverse/arbitrary language pairs would need a separate translation model).
- **`dictate-translate`** helper script + a `TRANSLATE` daemon command; the daemon publishes
  the flag to `$XDG_RUNTIME_DIR/dictation.translate` so the indicator switch always reflects
  the real state.

### Changed
- **Indicator menu opens on click; no more accidental dictation.** A click now opens the menu
  instead of toggling dictation directly. The menu has a single state-aware item, **Start
  dictation** when idle, **Stop dictation** while listening (greyed during transcription), so
  you can't start a session twice. (Cancel removed; Stop transcribes and inserts.)

## [0.3.6] - 2026-06-22

### Changed
- **Installer reclaims ~1.5GB.** The full-precision medium model is now deleted after it is
  quantized to q5_0 (the only model that actually runs), cutting the on-disk model footprint
  from ~2GB to ~514MB. The installer and README now state the disk (~1GB total) and RAM
  (~0.5GB, model hot while running) cost up front.

### Internal
- `__version__` in `dicti/__init__.py` is now the single source of truth; `pyproject.toml`
  derives its version from it dynamically (`[tool.setuptools.dynamic]`).

## [0.3.5] - 2026-06-17

### Added
- **Animated panel indicator.** The GNOME Shell extension now draws a custom five-bar glyph
  with Cairo, animated per state: a static "mic" trapezoid when idle, an organic equalizer
  bounce while listening, a left-to-right fill while transcribing (deep-green + pink brand
  colors). The animation timer only runs while active, so idle costs nothing. The optional
  AppIndicator (KDE/other desktops) uses matching static SVGs (`src/dicti/icons/`).
- **Brand assets** in `branding/` (app-icon tile + per-state marks) and a README hero with a
  synthetic demo GIF of the indicator cycling through its states.
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
- **Notifications are quiet by default.** New `notify_level` config
  (`error` default | `off` | `all`): the per-dictation "done"/status popups are gone (the
  animated icon already shows state, and they lit the clock's unread-notification dot). Only
  genuine failures (transcription error, whisper-on-CPU) notify at the default level.
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
