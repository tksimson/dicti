#!/bin/bash
# Phase 1: Install keyd config and enable the service.
# Backs up any existing /etc/keyd/default.conf before writing. Idempotent.

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo: sudo bash $0"
  exit 1
fi

REPO_ROOT="$(dirname "$(dirname "$(readlink -f "$0")")")"
SRC="$REPO_ROOT/keyd/default.conf"
DST=/etc/keyd/default.conf

if [[ ! -f "$SRC" ]]; then
  echo "Source config not found: $SRC"
  exit 1
fi

mkdir -p /etc/keyd

if [[ -f "$DST" ]] && ! cmp -s "$SRC" "$DST"; then
  BACKUP="${DST}.bak.$(date +%Y%m%d-%H%M%S)"
  cp "$DST" "$BACKUP"
  echo "==> Backed up existing config to $BACKUP"
fi

install -m 0644 "$SRC" "$DST"
echo "==> Installed $DST"

systemctl enable keyd
systemctl restart keyd
sleep 1
systemctl --no-pager status keyd | head -15

echo
echo "==> keyd active."
echo
echo "    !!! PANIC COMBO: hold Backspace+Escape+Enter together to kill keyd !!!"
echo "    !!! Test this NOW before relying on the new config.                !!!"
echo
echo "    NEXT verify your key emits the expected chord:"
echo "      sudo evtest        (pick your keyboard, watch for KEY_F23 / modifiers)"
echo "    or use 'wev' under Wayland."
echo
echo "    If the key doesn't emit f23, edit keyd/default.conf and re-run this script."
