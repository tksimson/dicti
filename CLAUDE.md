# dicti

Offline live dictation for Linux: tap a key, speak, the text lands in the focused window. whisper.cpp runs locally; nothing leaves the machine. Public, MIT. Human contributor rules: [CONTRIBUTING.md](CONTRIBUTING.md).

## The invariant

**Audio and transcripts never leave the machine, and never sit where another user can read them.** No network call except to the local whisper-server.

## Shape

- `src/dicti/daemon.py` = socket listener, recorder (`pw-record`), streaming commit logic, insertion. `insert.py` = clipboard, ydotool, wtype backends (spec 0001). `indicator.py` = tray.
- Three user services in `systemd/`: `whisper-server` (model hot in RAM, Vulkan), `dictation` (the daemon), `dicti-indicator`.
- Any user service that needs the GPU starts after `graphical-session.target` and probes Vulkan in `ExecStartPre`; started earlier, whisper-server silently falls back to CPU at 4-5x realtime.
- Design before changing core behavior: `specs/0001`, `specs/0002`, `docs/v0.3-streaming.md`. Open problems: `ROADMAP.md`.

## Run and test

```bash
bash install/install.sh                                  # full stack, phases 00..07
systemctl --user restart dictation.service               # pick up edits in src/
journalctl --user -u dictation -u whisper-server -f
PYTHONPATH=src python3 -m pytest -q                      # pure stdlib, no audio, no keystrokes
ruff check src tests
```

Tests share one fake `requests` (`tests/_fake_requests.py`). Patch a dependency on the dicti module that uses it (`ins.time = ...`), never the stdlib module itself: that leaks into every later test.

## Branches and release

- PRs against `dev`; `main` = the latest release.
- User-facing change = a `CHANGELOG.md` entry. Release = version bump in `src/dicti/__init__.py` + changelog + tag.
