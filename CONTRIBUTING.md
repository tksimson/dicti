# Contributing to dicti

Thanks for taking a look. dicti is a small, offline dictation tool for Linux and
contributions of all sizes are welcome, from a typo fix to a whole new install
target or desktop integration.

This is a young project, so if something here is unclear or gets in your way,
opening an issue to say so is itself a useful contribution.

## Ways to help

- **Report a bug** or **request a feature** via [Issues](https://github.com/tksimson/dicti/issues).
  There are templates for both.
- **Share that it works (or doesn't) on your setup.** dicti is tested mainly on
  Debian/Ubuntu + GNOME Shell. Reports from other distros, desktops (KDE, wlroots),
  and GPUs are genuinely valuable.
- **Send a pull request.** See below.

## Branches

- `main` = the latest released version. Stable.
- `dev` = integration branch for the next release. **Open your PRs against `dev`.**

You don't need any special access. Fork the repo, branch in your fork, and open a
PR. There's no need to ask first for small fixes; for anything large, opening an
issue to discuss the approach first saves everyone time.

## Running from source

dicti runs straight from the source tree (it is not installed via pip). The full
stack needs whisper.cpp and a few system packages, set up by the install scripts:

```bash
git clone https://github.com/tksimson/dicti.git
cd dicti
bash install/install.sh   # phases 00..07, see README for what each does
```

The daemon and indicator run as systemd user services that point at this repo's
`src/` directory, so your edits take effect after a restart:

```bash
systemctl --user restart dictation.service
journalctl --user -u dictation -u whisper-server -f   # live logs
```

## Tests

The test suite is pure stdlib (no real keystrokes or audio):

```bash
PYTHONPATH=src python3 -m pytest -q
# or run a file directly:
python3 tests/test_insert.py
```

Please run the tests before opening a PR, and add tests when you change insertion
or streaming behavior.

## Pull request notes

- Keep PRs focused on one thing. Smaller is easier to review and merge.
- Match the surrounding code style; no large reformatting in a feature PR.
- Describe what changed and why, and how you tested it (which distro/desktop/GPU).
- Update `CHANGELOG.md` and the relevant docs if your change is user-facing.

## Design context

Before changing core behavior, the design docs are worth a read: `specs/0001`,
`specs/0002`, and `docs/v0.3-streaming.md`. The `ROADMAP.md` shows where things
are heading and which problems are still open.

## Licensing

By contributing, you agree that your contributions are licensed under the
project's [MIT License](LICENSE).
