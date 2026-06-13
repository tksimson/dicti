#!/bin/bash
# Phase 5b: Bind a GNOME custom shortcut to dictate-toggle.
# Super+Shift+Alt+F12 -> dictate-toggle (TOGGLE; daemon flips state).
# Run as your normal user (NOT sudo).

set -euo pipefail

if [[ $EUID -eq 0 ]]; then
  echo "Run as your normal user (without sudo)."
  exit 1
fi

if ! command -v gsettings >/dev/null; then
  echo "gsettings not found, this script targets GNOME. Bind the shortcut manually otherwise."
  exit 1
fi

CMD="$HOME/.local/bin/dictate-toggle"
[[ -x "$CMD" ]] || { echo "Missing $CMD, run 04-install-daemon.sh first"; exit 1; }

SCHEMA="org.gnome.settings-daemon.plugins.media-keys"
PATH_PREFIX="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"
TOGGLE_PATH="$PATH_PREFIX/dictate-toggle/"

echo "==> Registering custom-keybindings list"
gsettings set "$SCHEMA" custom-keybindings "['$TOGGLE_PATH']"

echo "==> Binding Super+Shift+Alt+F12 -> dictate-toggle (TOGGLE)"
# The Copilot key (e.g. Lenovo) natively emits Super+Shift+F23 (Microsoft AI-key
# standard). keyd remaps F23 -> Super+Alt+F12; Super and Shift pass through, so
# GNOME receives Super+Shift+Alt+F12. Adjust if your key/remap differs.
SUB_SCHEMA="org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
gsettings set "$SUB_SCHEMA:$TOGGLE_PATH" name 'Dictation Toggle'
gsettings set "$SUB_SCHEMA:$TOGGLE_PATH" command "$CMD"
gsettings set "$SUB_SCHEMA:$TOGGLE_PATH" binding '<Super><Shift><Alt>F12'

echo
echo "==> Verify in: Settings -> Keyboard -> View and Customize Shortcuts -> Custom Shortcuts"
echo
echo "==> END-TO-END TEST"
echo "    1. Focus GNOME Text Editor or any text input"
echo "    2. Tap your dictation key   (daemon goes IDLE -> LISTENING)"
echo "    3. Speak: 'to jest test polskiego rozpoznawania mowy ąęłóśżźćń'"
echo "    4. Tap again  (daemon: LISTENING -> PROCESSING -> IDLE, types the text)"
echo
echo "    Watch logs:  journalctl --user -u dictation -u whisper-server -f"
