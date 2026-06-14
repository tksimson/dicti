# dicti Roadmap

dicti is a local, offline live-dictation tool for Linux. The aim: the
best-in-class push-to-talk dictation experience on Linux, GNOME first, then
broader desktops and distros.

## v0.2, Daily-driver fixes (current)

The everyday-pain release. All shipped:

- **Long sessions**, `max_record_sec` raised to 1 hour (was a 60s hard cap that
  cut people off mid-sentence).
- **Silence auto-stop**, a monitor samples the recording's RMS and stops after
  `silence_timeout_sec` (default 180s) of real silence, instead of a blind timer.
- **Universal text insertion**, transcript is typed via `ydotool type` (works in
  plain editors, IDEs, terminals; no Markdown-render-on-paste), clipboard kept as
  a safety net.
- **Subtle tray indicator**, top-bar AppIndicator with idle / listening /
  transcribing states; the "listening" popup is gone.
- **Config file**, `~/.config/dicti/config.toml` for timeouts, language, insertion
  method and silence thresholds.
- **Repo**, became the public MIT project (ported from a private prototype).

## v0.3, Live streaming with VAD (shipped)

Goal met: text appears **as you speak** while keeping batch-grade quality.

- **Growing-window streaming**, each pass (every `stream_interval_sec`) re-transcribes the
  whole utterance so far, so whisper always has full context (= batch quality), and types
  only the words that have **stabilised** across passes. **Append-only**: it never
  backspaces, so it can't corrupt text behind the cursor if focus moves. `max_context_sec`
  bounds the per-pass cost on long dictations.
- **No VAD; stability filters hallucinations**, a word is typed only once it agrees across
  two passes, so silence hallucinations (which vary pass to pass) never commit, and the
  blocklist drops the stock ones. Server-side VAD was tried and reverted: it trimmed quiet
  speech onsets, eating the first word after each pause on a low-output mic.
- **Capture-live gate**, the red indicator waits until pw-record is actually recording, so a
  fast speaker doesn't lose their first word.
- **Batch mode kept** as a one-line config fallback (`mode = "batch"`).

Found along the way: chunked streaming destroyed whisper's context and tanked quality
(reverted to the growing-window design above); auto language-detect is most reliable with
full context, so the window matters for mixed-language use too.

## v0.4, Word-level refinement & polish (next)

Build on the streaming loop toward macOS-grade, **self-correcting** dictation.

- **Language picker in the indicator menu**: a small preferences popup from the top-bar
  indicator to choose the Whisper language (auto / pl / en / ...) without editing the config
  and restarting, with an optional per-session lock for soft/ambiguous audio.
- **Committed vs tentative** text: keep append-only for stable words, but **backspace-correct
  the still-tentative tail** as it firms up, for lower-latency display. Gate carefully on X11
  focus (ydotool types into the focused window; pause insertion when focus changes) so
  corrections never eat the wrong text. This is the risky bit v0.3 intentionally skipped.
- **Smarter window anchoring**: anchor on real utterance boundaries instead of the
  time-based `max_context_sec` re-anchor (e.g. silero VAD used only to find boundaries, never
  to trim the audio sent to whisper, so onsets stay intact).
- **Smart line breaks**: detect real sentence/paragraph boundaries and insert newlines
  deliberately, instead of v0.2.1's blanket newline-collapse.

## Future, Reach & polish

- **Capture-to-file mode**: hold Shift when starting/stopping a recording to send the
  transcript to a **new file** instead of typing into the focused window, with a save
  dialog (e.g. `zenity --file-selection --save`) on stop, to spin up a fresh `.md`/`.txt`
  on the fly. Clean because it's just a different text *sink* (file vs keystrokes); the
  wrinkle is plumbing the Shift modifier from keyd/GNOME through the socket as a flag
  (e.g. `START_NEWFILE`).
- **Wayland** insertion and clipboard (`wtype` / `wl-copy`) as alternatives to
  `ydotool`/`xclip`; detect session type.
- **Non-PipeWire** audio fallback (ALSA/`arecord`).
- **Non-systemd** init support; packaging as **pipx**, **.deb**, and **AUR**.
- **Other desktops** (KDE/Plasma indicator, generic tray).
- Colored/custom indicator icons; optional sound cues.
- Per-app insertion profiles; custom vocabulary / punctuation commands.
- Model selection (tiny..large) and download helper from config.
- **Language preferences pane**: pick which Whisper languages to use (e.g. Polish +
  English), with optional per-session lock for soft/ambiguous audio.

## Non-goals

- Cloud/online transcription. dicti is offline by design.
- A heavyweight GUI app. It stays a lean daemon + tray indicator.
