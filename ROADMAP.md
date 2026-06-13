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

## v0.3, Mac-like live streaming (next, biggest piece)

Goal: text appears and **self-corrects as you speak**, like macOS dictation,
instead of arriving all at once at the end.

- Pipe `pw-record` PCM to the daemon and keep a rolling audio buffer.
- **VAD (voice activity detection)**: run whisper-server with `--vad` + a silero VAD model
  so silent stretches are never fed to the model. This is the robust fix for silence
  hallucinations and for the "missed a quiet sentence at the end of a long mostly-silent
  recording" case that batch transcription handles poorly (v0.2.1's energy gate only
  skips wholly-silent recordings).
- Every ~2-3s, re-transcribe a sliding/growing window so longer context refines
  earlier words (whisper is far more accurate with more context).
- Maintain a **committed vs tentative** text model; type committed deltas live and
  backspace-correct tentative words as they firm up.
- Tune chunk/window sizes for the latency-vs-accuracy trade-off.
- **Smart line breaks**: detect real sentence/paragraph/discussion boundaries and insert
  newlines deliberately, instead of v0.2.1's blanket newline-collapse.
- This naturally removes the "can't start while transcribing" limitation, since
  there's no separate batch PROCESSING phase.

Risk: per-chunk accuracy is lower than whole-file batch unless the
overlapping-context rewrite is done well. That's why it's its own release.

## Future, Reach & polish

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
