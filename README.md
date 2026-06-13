# dicti

Local, offline **live dictation for Linux**. Tap a key, talk, tap again — your
words are transcribed by [whisper.cpp](https://github.com/ggerganov/whisper.cpp)
on your own machine and typed into whatever window has focus. No cloud, no
account, no network. Built and tested on Debian + GNOME (X11).

> Status: **v0.2 (alpha).** Works well day-to-day; rough edges remain. See the
> [ROADMAP](ROADMAP.md). Contributions welcome.

## Features

- **Push-to-talk** via a global key (the "Copilot"/AI key, or any key you bind).
- **Fully offline** — whisper.cpp medium model, GPU-accelerated via Vulkan.
- **Long sessions** — record for as long as you talk (1-hour safety cap).
- **Silence auto-stop** — ends ~3 minutes after you actually go quiet (configurable).
- **Universal text insertion** — types the transcript with `ydotool`, so it works
  in plain editors, IDEs and terminals alike (no "paste renders my Markdown" surprise).
  The transcript is also left on the clipboard as a safety net.
- **Subtle tray indicator** — a top-bar icon shows idle / listening / transcribing.
  No nagging popups.
- **Multilingual** — auto language detection (e.g. English + Polish).

## How it works

```
[your key] --keyd--> Super+Shift+Alt+F12 --GNOME shortcut--> dictate-toggle
     --unix socket--> dictation daemon --pw-record--> /tmp WAV
     --HTTP--> whisper-server (Vulkan) --> transcript --ydotool type--> focused window
```

Three user services: `whisper-server` (model hot in RAM), `dictation` (the daemon),
and `dicti-indicator` (the tray icon). State is mirrored to
`$XDG_RUNTIME_DIR/dictation.state` so the indicator can follow the daemon.

## Requirements

- Debian/Ubuntu-family distro (apt). PipeWire for audio (`pw-record`).
- A Vulkan-capable GPU (an integrated GPU is fine). CPU fallback exists but is ~4-5× slower.
- GNOME with the AppIndicator extension (installed by the preflight script) for the tray icon.
- Key packages (installed automatically): `keyd`, `ydotool`, `xclip`, `libnotify-bin`,
  `python3-gi`, `gir1.2-ayatanaappindicator3-0.1`, plus a Vulkan toolchain.

## Install

```bash
git clone https://github.com/<you>/dicti.git
cd dicti
bash install/install.sh
```

The guided installer runs six phases (system packages, keyd remap, build
whisper.cpp + download/quantize the model, install the three user services,
ydotool, and the GNOME shortcut). You will be asked to log out/in once after the
first phase so `input`-group membership takes effect. Each phase is also runnable
on its own from `install/00..06`.

If your dictation key isn't a Copilot/AI key, run `sudo evtest` (or `wev` on
Wayland) to find its `KEY_*` name and edit `keyd/default.conf` accordingly.

## Usage

- Tap your bound key → **listening** (tray icon turns to a record dot).
- Speak. Pause to think freely; it won't cut off until ~3 min of real silence.
- Tap again → **transcribing** (spinner) → the text is typed at your cursor.
- `dictate-toggle [START|STOP|TOGGLE|CANCEL|STATUS]` controls the daemon from the CLI.
- The tray menu offers Toggle / Cancel.

## Configuration

Copy and edit `~/.config/dicti/config.toml` (the installer seeds one from
[`config/config.toml.example`](config/config.toml.example)). Keys include
`silence_timeout_sec`, `max_record_sec`, `language`, `paste_method`
(`type` or `clipboard`), `key_delay_ms`, and the silence-detection thresholds.
Restart the daemon after editing: `systemctl --user restart dictation`.

## Troubleshooting

- **Slow transcription / "Dictation degraded" popup** — whisper-server fell back to
  CPU. `systemctl --user restart whisper-server` once the graphical session is up;
  check `journalctl --user -u whisper-server`.
- **Nothing types** — ensure `ydotoold` is running and `YDOTOOL_SOCKET` is set
  (`systemctl --user status ydotool`); you must be in the `input` group (log out/in
  after install).
- **No tray icon** — enable the AppIndicator GNOME extension once via the Extensions app.
- **Live logs** — `journalctl --user -u dictation -u whisper-server -f`.

## License

MIT — see [LICENSE](LICENSE). Uses OpenAI's Whisper model via whisper.cpp; respect
the model's license/terms.
