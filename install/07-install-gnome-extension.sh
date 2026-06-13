#!/bin/bash
# Phase 7: Install the dicti GNOME Shell extension (single top-bar indicator).
# This replaces the optional AppIndicator-based indicator, so no other apps'
# tray icons are pulled in. Run as your normal user (NOT sudo).

set -euo pipefail

if [[ $EUID -eq 0 ]]; then
  echo "Run as your normal user (without sudo)."
  exit 1
fi

REPO_ROOT="$(dirname "$(dirname "$(readlink -f "$0")")")"
UUID="dicti@local"
SRC="$REPO_ROOT/gnome-extension/$UUID"
DST="$HOME/.local/share/gnome-shell/extensions/$UUID"

[[ -d "$SRC" ]] || { echo "Missing extension source: $SRC"; exit 1; }

mkdir -p "$(dirname "$DST")"
rm -rf "$DST"
cp -r "$SRC" "$DST"
echo "==> Installed extension to $DST"

# Retire the optional AppIndicator-based indicator (this extension replaces it).
systemctl --user disable --now dicti-indicator.service 2>/dev/null || true

echo
echo "==> Reload GNOME Shell so it discovers the extension:"
echo "      X11:     press Alt+F2, type 'r', press Enter"
echo "      Wayland: log out and back in"
echo
echo "==> Then enable it:"
echo "      gnome-extensions enable $UUID"
echo "    (or via the Extensions app). Trying now in case the shell already sees it:"
gnome-extensions enable "$UUID" 2>/dev/null && echo "    enabled." \
  || echo "    not yet visible — reload the shell first, then run the enable command above."
echo
echo "==> Once dicti shows its own icon, you can turn OFF the generic"
echo "    'AppIndicator and KStatusNotifierItem Support' extension if you only"
echo "    enabled it for dictation."
