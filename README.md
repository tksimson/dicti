# dicti

Local, offline live dictation for Linux. Tap a key, talk, and your words appear as you
speak, transcribed by [whisper.cpp](https://github.com/ggerganov/whisper.cpp) on your own
machine and typed into whatever window has focus. No cloud, no account, no network.

I built this because I was used to a good dictation app on the Mac and wanted the same thing
on Linux. Tested on Debian + GNOME (X11).

> Status: v0.3 (alpha). Live streaming dictation; works well day to day, rough edges remain.
> See the [ROADMAP](ROADMAP.md).

## Features

- Push-to-talk via a global key (the "Copilot"/AI key, or any key you bind).
- **Live streaming**: text appears as you speak, refined with full context (whisper
  re-transcribes the whole utterance each pass, so quality matches batch). Append-only, so
  it never rewrites text behind your cursor. Batch mode is one config line away (`mode =
  "batch"`).
- **No silence hallucinations**: whisper-server runs with silero VAD (padded so it doesn't
  clip the first word), and a word must also repeat across passes before it's typed, so the
  stock "thanks for watching" guesses on pauses never reach the screen.
- Fully offline: whisper.cpp medium model, GPU-accelerated via Vulkan.
- Long sessions (1-hour cap) with silence auto-stop after a few minutes of real quiet.
- Universal insertion: types the transcript with `ydotool`, so it works in plain editors,
  IDEs and terminals alike. The transcript is also left on the clipboard as a safety net.
- A single top-bar indicator (GNOME Shell extension): idle / listening / transcribing.
- Multilingual auto-detect (e.g. English + Polish).

## How it works

```
[your key] -> keyd -> Super+Shift+Alt+F12 -> GNOME shortcut -> dictate-toggle
   -> unix socket -> dictation daemon -> pw-record -> /tmp WAV
   -> HTTP -> whisper-server (Vulkan) -> transcript -> ydotool type -> focused window
```

In streaming mode the daemon re-transcribes the whole utterance so far every ~2s (whisper
always has full context, so quality matches batch) and types only the words that have
stabilised across passes. It is append-only, so text already typed is never rewritten.
whisper-server's VAD drops silence inside the window (padded so quiet onsets survive), and
the repeat-across-passes rule is a second filter against hallucinations.

Two user services (`whisper-server`, `dictation`) plus the GNOME Shell extension
`dicti@local` for the indicator. The daemon mirrors its state to
`$XDG_RUNTIME_DIR/dictation.state` so the indicator can follow it.

## Requirements

- Debian/Ubuntu-family distro (apt), PipeWire audio (`pw-record`).
- A Vulkan-capable GPU (integrated is fine). CPU fallback works but is ~4-5x slower.
- GNOME Shell (tested on 48) for the indicator extension.
- `xclip` and `xprop` (x11-utils): used to insert accented/non-ASCII characters like Polish
  ąęóśżźćń via a paste (ydotool 1.x can only type ASCII keycodes), choosing Ctrl+V or
  Ctrl+Shift+V based on the focused app. The installer pulls them in.

## Install

```bash
git clone https://github.com/tksimson/dicti.git
cd dicti
bash install/install.sh
```

The guided installer runs the phases in order (system packages, keyd remap, build
whisper.cpp + download/quantize the model, the user services, ydotool, the GNOME shortcut,
the indicator extension). You will be asked to log out/in once after the first phase so
`input`-group membership takes effect. Each phase is also runnable on its own from
`install/00..07`.

If your dictation key isn't a Copilot/AI key, run `sudo evtest` (or `wev` on Wayland) to
find its `KEY_*` name and edit `keyd/default.conf`.

## Usage

- Tap your bound key to start listening, tap again to transcribe and insert.
- Pause to think freely; it won't cut off until a few minutes of real silence.
- `dictate-toggle [START|STOP|TOGGLE|CANCEL|STATUS]` controls the daemon from the CLI.
- Left-click the indicator to toggle, right-click for a menu.

## Configuration

Copy and edit `~/.config/dicti/config.toml` (the installer seeds one from
[`config/config.toml.example`](config/config.toml.example)): `mode` (`streaming` or
`batch`) and the streaming phrase tuning, `silence_timeout_sec`, `max_record_sec`,
`language`, `paste_method`, the silence thresholds, and the transcript cleanup flags.
Restart after editing: `systemctl --user restart dictation`.

Tip: whisper transcribes one language per pass. `language = "auto"` works well for mixed
use now that streaming keeps full context, but if a quiet or ambiguous voice gets detected
wrong, pin it, e.g. `language = "pl"`.

## Troubleshooting

- Slow transcription / "Dictation degraded" popup: whisper-server fell back to CPU. Run
  `systemctl --user restart whisper-server`; check `journalctl --user -u whisper-server`.
- Nothing types: make sure `ydotoold` runs and `YDOTOOL_SOCKET` is set, and that you are in
  the `input` group (log out/in after install).
- No top-bar icon: reload GNOME Shell (Alt+F2, `r` on X11; log out/in on Wayland), then
  `gnome-extensions enable dicti@local`.
- Live logs: `journalctl --user -u dictation -u whisper-server -f`.

## License

MIT, see [LICENSE](LICENSE). Uses OpenAI's Whisper model via whisper.cpp; respect the
model's license/terms.
