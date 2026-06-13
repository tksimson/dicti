#!/bin/bash
# dicti guided installer. Runs the numbered phases in order, using sudo only
# where required. Idempotent — safe to re-run. Run as your normal user.
#
#   bash install/install.sh
#
# You will be prompted for your sudo password for phases 0 and 1, and asked to
# log out/in after phase 0 so 'input' group membership takes effect.

set -euo pipefail

if [[ $EUID -eq 0 ]]; then
  echo "Run as your normal user (without sudo); the script calls sudo itself."
  exit 1
fi

HERE="$(dirname "$(readlink -f "$0")")"
cd "$HERE"

run() { echo; echo "########## $1 ##########"; shift; "$@"; }

run "Phase 0: system packages + uinput (sudo)"      sudo bash 00-preflight.sh

echo
read -rp "Phase 0 added you to the 'input' group. If this is the first run, log out/in now and re-run. Continue anyway? [y/N] " ans
[[ "${ans,,}" == "y" ]] || { echo "Stopping. Re-run after logout/login."; exit 0; }

run "Phase 1: keyd remap (sudo)"                     sudo bash 01-install-keyd.sh
run "Phase 2: build whisper.cpp + model"             bash 02-build-whisper.sh
run "Phase 3: whisper-server user service"           bash 03-install-whisper-server.sh
run "Phase 4: dictation daemon + indicator"          bash 04-install-daemon.sh
run "Phase 5a: ydotool user service"                 bash 05-install-ydotool.sh
run "Phase 5b: GNOME shortcut binding"               bash 06-bind-shortcuts.sh

echo
echo "==> Install complete. Tap your dictation key in a focused text field to try it."
echo "    Logs: journalctl --user -u dictation -u whisper-server -f"
