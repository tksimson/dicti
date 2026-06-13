#!/bin/bash
# Phase 4: Install dictate-toggle + the dictation daemon and tray indicator
# user services. Run as your normal user (NOT sudo).

set -euo pipefail

if [[ $EUID -eq 0 ]]; then
  echo "Run as your normal user (without sudo)."
  exit 1
fi

REPO_ROOT="$(dirname "$(dirname "$(readlink -f "$0")")")"
SRC_DIR="$REPO_ROOT/src"
UNIT_DIR="$HOME/.config/systemd/user"

mkdir -p "$HOME/.local/bin" "$UNIT_DIR"

install -m 0755 "$REPO_ROOT/bin/dictate-toggle" "$HOME/.local/bin/dictate-toggle"
echo "==> Installed ~/.local/bin/dictate-toggle"

# Render systemd units, substituting @SRC@ with this repo's src/ dir so the
# units are machine-independent in the repo but correct once installed.
for unit in dictation.service dicti-indicator.service; do
  sed "s|@SRC@|$SRC_DIR|g" "$REPO_ROOT/systemd/$unit" > "$UNIT_DIR/$unit"
  echo "==> Installed ~/.config/systemd/user/$unit"
done

# Seed a user config from the example if none exists (purely optional to edit).
CFG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/dicti"
if [[ ! -f "$CFG_DIR/config.toml" ]]; then
  mkdir -p "$CFG_DIR"
  cp "$REPO_ROOT/config/config.toml.example" "$CFG_DIR/config.toml"
  echo "==> Seeded $CFG_DIR/config.toml (defaults; edit to taste)"
fi

# Make sure ~/.local/bin is on PATH
case ":$PATH:" in
  *":$HOME/.local/bin:"*) : ;;
  *) echo "    NOTE: $HOME/.local/bin not on \$PATH; add it to ~/.bashrc if needed" ;;
esac

systemctl --user daemon-reload
systemctl --user enable dictation.service
systemctl --user restart dictation.service
# Note: dicti-indicator.service (AppIndicator) is installed but NOT enabled by
# default, the GNOME Shell extension (phase 7) is the preferred indicator. The
# AppIndicator service stays available for non-GNOME desktops.

sleep 1
systemctl --user --no-pager status dictation.service | head -12

echo
echo "==> Manual smoke test (focus a text editor first, then run):"
echo "      dictate-toggle START   # speak something"
echo "      dictate-toggle STOP    # transcribed text should type into the focused window"
echo
echo "    NEXT: bash 05-install-ydotool.sh   (if not already done)"
echo "    THEN: bash 06-bind-shortcuts.sh"
echo "    THEN: bash 07-install-gnome-extension.sh   (top-bar indicator)"
