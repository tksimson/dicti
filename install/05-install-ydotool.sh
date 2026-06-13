#!/bin/bash
# Phase 5a: Use the Debian-shipped ydotool.service (USER-level).
# The 'ydotool' apt package installs and enables ydotool.service automatically;
# this script verifies it, ensures YDOTOOL_SOCKET is exported, and smoke-tests typing.
# Run as your normal user (NOT sudo).

set -euo pipefail

if [[ $EUID -eq 0 ]]; then
  echo "Run as your normal user (without sudo)."
  exit 1
fi

echo "==> Verifying Debian-shipped ydotool.service"
if ! systemctl --user list-unit-files ydotool.service 2>/dev/null | grep -q ydotool; then
  echo "ydotool.service not found, is the 'ydotool' apt package installed?"
  exit 1
fi

systemctl --user enable ydotool.service
systemctl --user restart ydotool.service
sleep 1
systemctl --user --no-pager status ydotool.service | head -10

SOCK="${XDG_RUNTIME_DIR}/.ydotool_socket"
if [[ ! -S "$SOCK" ]]; then
  echo "==> Socket not at $SOCK; checking unit ExecStart for actual path"
  systemctl --user cat ydotool.service | grep -E 'ExecStart|socket' | head -5
fi

# Make YDOTOOL_SOCKET available to shells and to the systemd user environment
SOCK_LINE='export YDOTOOL_SOCKET="$XDG_RUNTIME_DIR/.ydotool_socket"'
if ! grep -qF "$SOCK_LINE" "$HOME/.bashrc" 2>/dev/null; then
  echo "$SOCK_LINE" >> "$HOME/.bashrc"
  echo "==> Added YDOTOOL_SOCKET export to ~/.bashrc"
fi
export YDOTOOL_SOCKET="$XDG_RUNTIME_DIR/.ydotool_socket"
systemctl --user import-environment YDOTOOL_SOCKET || true

echo
echo "==> Smoke test: in 3 seconds, ydotool will type 'hello' into the FOCUSED window."
echo "    Focus a safe text input (e.g. an editor) NOW."
sleep 3
ydotool type "hello" || echo "    (typing failed, check 'groups | grep input' and try logout/login)"

echo
echo "    NEXT: bash 06-bind-shortcuts.sh"
