# dicti Roadmap

dicti is a local, offline live-dictation tool for Linux. The aim: the best-in-class
push-to-talk dictation experience on Linux, GNOME first, then broader desktops and distros.

**You are here:** v0.3.5 shipped, live streaming, a calm animated indicator, and settled text
insertion. v0.4 is next. The full shipped history is folded in at the bottom.

> v0.2 daily-driver fixes &rarr; v0.3 live streaming + VAD &rarr; v0.3.5 identity & calm &rarr; **v0.4 word-level refinement (next)**

## Next: v0.4, Word-level refinement & polish

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

## Later: reach & polish

- **Capture-to-file mode**: hold Shift when starting/stopping a recording to send the
  transcript to a **new file** instead of typing into the focused window, with a save
  dialog (e.g. `zenity --file-selection --save`) on stop, to spin up a fresh `.md`/`.txt`
  on the fly. Clean because it's just a different text *sink* (file vs keystrokes); the
  wrinkle is plumbing the Shift modifier from keyd/GNOME through the socket as a flag
  (e.g. `START_NEWFILE`).
- **Insertion backends** (spec 0001, v1 shipped): pluggable `clipboard` (X11 + Wayland via
  `wl-clipboard`) / `wtype` (wlroots) / `ydotool`. Next: validate on real Wayland/wlroots
  hardware. (The **IBus engine**, spec 0002, was spiked and **rejected**: it broke the user's
  Polish XKB layout and still could not inject into Zed's non-standard terminal.)
- **Integrated terminals** (Zed/VS Code): accented text doesn't paste, but it is fixable.
  Diagnosis (0.3.5): a *manual* Ctrl+Shift+V pastes Polish into Zed's terminal fine, so the
  clipboard path works. dicti sends plain Ctrl+V because Zed reports one window class
  (`dev.zed.Zed`) for both the editor and terminal panes, so focus-based auto-detection can't
  tell which pane is active. Planned fix: a per-app paste-shortcut override (force
  ctrl+shift+v for known editor-with-terminal apps), accepting it then mis-fires in those
  apps' *editor* panes. Post-launch.
- **Non-PipeWire** audio fallback (ALSA/`arecord`).
- **Non-systemd** init support; packaging as **pipx**, **.deb**, and **AUR**.
- **Other desktops** (KDE/Plasma indicator, generic tray).
- Optional sound cues on start/stop. (Colored/animated indicator icons shipped in v0.3.5.)
- Per-app insertion profiles; custom vocabulary / punctuation commands.
- Model selection (tiny..large) and download helper from config.
- **Language preferences pane**: pick which Whisper languages to use (e.g. Polish +
  English), with optional per-session lock for soft/ambiguous audio.

## Ideas to weigh later (not soon)

Worth holding, not building yet. dicti owns something no clipboard manager does, the dictation
stream, and already keeps the last transcript (`bin/dictate-last`, `~/.cache/dicti/last.txt`).
A few directions grow from that. None is v0.4. The standing threat is feature creep, so the
guiding principle is **doing less, better**: the bar for adding any of this is whether it makes
the core (best-in-class Linux dictation) *better*, not just *bigger*.

- **Dictation history**: keep recent dictations so you can re-paste them. Open question on
  scope, just the **last ~10** on the indicator menu (small, lean), or a **searchable library**
  of everything you've dictated (more powerful, more app). Start small, if at all.
- **Variations per utterance**: dicti produces both the live-streamed text and the full-context
  "perfect" version of each utterance; keeping those lets you pick the best rendering. This one
  is genuinely differentiated, it falls out of how dicti already works.
- **Clipboard + dictation together**: an open question, not a decision. Whether to grow a
  clipboard history *into* dicti, or keep dicti and a dedicated clipboard manager (CopyQ,
  GPaste, Clipboard Indicator) **separate** and let each do one thing well. Weigh this only
  if/when the dictation history proves its worth.

## Non-goals

- Cloud/online transcription. dicti is offline by design.
- A heavyweight GUI app. It stays a lean daemon + tray indicator; anything like history would
  ride the menu + a fuzzy finder before it ever became a bespoke UI.

## Shipped so far

<details>
<summary><b>v0.3.5</b> &middot; Identity & calm: animated brand indicator, quiet by default, insertion backends settled</summary>

<br>

The "looks like a real product" release.

- **Animated bar indicator**, the GNOME Shell extension draws a custom five-bar glyph (Cairo):
  static "mic" trapezoid when idle, an organic equalizer bounce while listening, a
  left-to-right fill while transcribing, in the deep-green + pink brand colors. The animation
  timer runs only while active, so idle costs nothing. Matching static SVGs back the optional
  AppIndicator on KDE/other desktops. Brand assets + a demo GIF now front the README.
- **Quiet by default**, new `notify_level` config (`error` default | `off` | `all`) removes the
  per-dictation "done"/status popups (which also lit GNOME's unread-notification dot); only
  genuine failures (transcription error, whisper-on-CPU) notify.
- **Insertion backends settled** (spec 0001): clipboard default everywhere, `wtype` on wlroots,
  `ydotool` ASCII fallback, documented as honest support tiers (GNOME/Xorg tested; wlroots /
  other X11 / GNOME-Wayland testers-wanted).
- **Input-method fix**, documented that GNOME-Xorg + IBus is the native stack and Polish =
  the `pl` "programmers" XKB layout (the rejected IBus spike, spec 0002, had left it broken).

</details>

<details>
<summary><b>v0.3</b> &middot; Live streaming with VAD: text appears as you speak, at batch-grade quality</summary>

<br>

Goal met: text appears **as you speak** while keeping batch-grade quality.

- **Growing-window streaming**, each pass (every `stream_interval_sec`) re-transcribes the
  whole utterance so far, so whisper always has full context (= batch quality), and types
  only the words that have **stabilised** across passes. **Append-only**: it never
  backspaces, so it can't corrupt text behind the cursor if focus moves. `max_context_sec`
  bounds the per-pass cost on long dictations.
- **Server-side VAD, tuned for onsets** (`--vad-threshold 0.25 --vad-speech-pad-ms 500`),
  rejects silence (no hallucinations, no runaway session) while the generous padding keeps
  the first word after a pause, which a tighter VAD trims on a low-output mic. The
  stabilise-across-passes rule is a second line of defence.
- **Non-ASCII insertion**, ASCII is typed via ydotool; text with Polish/accented characters
  is inserted byte-exact via the clipboard (ydotool 1.x cannot type non-ASCII keycodes).
- **Capture-live gate**, the red indicator waits until pw-record is actually recording, so a
  fast speaker doesn't lose their first word.
- **Batch mode kept** as a one-line config fallback (`mode = "batch"`).

Found along the way: chunked streaming destroyed whisper's context and tanked quality
(reverted to the growing-window design above); a tight VAD trims quiet speech onsets while
no VAD lets silence hallucinations run away (settled on a loosely-padded VAD); and xdotool's
Unicode typing can deadlock X (use clipboard for non-ASCII instead).

</details>

<details>
<summary><b>v0.2</b> &middot; Daily-driver fixes: long sessions, silence auto-stop, universal insertion</summary>

<br>

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

</details>
