# dicti

Local, offline live dictation for Linux. Tap a key, talk, tap again, and your words are
transcribed by [whisper.cpp](https://github.com/ggerganov/whisper.cpp) on your own machine
and typed into whatever window has focus. No cloud, no account, no network.

I built this because I was used to a good dictation app on the Mac and wanted the same thing
on Linux. Tested on Debian + GNOME (X11).

> Status: v0.2 (alpha). Works well day to day, rough edges remain. See the [ROADMAP](ROADMAP.md).

## Features

- Push-to-talk via a global key (the "Copilot"/AI key, or any key you bind).
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

Two user services (`whisper-server`, `dictation`) plus the GNOME Shell extension
`dicti@local` for the indicator. The daemon mirrors its state to
`$XDG_RUNTIME_DIR/dictation.state` so the indicator can follow it.

## Requirements

- Debian/Ubuntu-family distro (apt), PipeWire audio (`pw-record`).
- A Vulkan-capable GPU (integrated is fine). CPU fallback works but is ~4-5x slower.
- GNOME Shell (tested on 48) for the indicator extension.

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
[`config/config.toml.example`](config/config.toml.example)): `silence_timeout_sec`,
`max_record_sec`, `language`, `paste_method`, the silence thresholds, and the transcript
cleanup flags. Restart after editing: `systemctl --user restart dictation`.

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
