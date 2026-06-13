#!/bin/bash
# Phase 3: Install whisper-server as a user systemd service.
# Run as your normal user (NOT sudo).

set -euo pipefail

if [[ $EUID -eq 0 ]]; then
  echo "Run as your normal user (without sudo)."
  exit 1
fi

REPO_ROOT="$(dirname "$(dirname "$(readlink -f "$0")")")"
SRC="$REPO_ROOT/systemd/whisper-server.service"
DST_DIR="$HOME/.config/systemd/user"
DST="$DST_DIR/whisper-server.service"

mkdir -p "$DST_DIR"
install -m 0644 "$SRC" "$DST"
echo "==> Installed $DST"

# Sanity: required files present
BIN="$HOME/opt/whisper.cpp/build/bin/whisper-server"
MODEL="$HOME/opt/whisper.cpp/models/ggml-medium-q5_0.bin"
[[ -x "$BIN" ]] || { echo "Missing: $BIN  (run 02-build-whisper.sh first)"; exit 1; }
[[ -f "$MODEL" ]] || { echo "Missing: $MODEL  (run 02-build-whisper.sh first)"; exit 1; }

systemctl --user daemon-reload
systemctl --user enable whisper-server.service
systemctl --user restart whisper-server.service

sleep 3
systemctl --user --no-pager status whisper-server.service | head -15

echo
echo "==> Smoke test (curl)"
SAMPLE="$HOME/opt/whisper.cpp/samples/jfk.wav"
if [[ -f "$SAMPLE" ]]; then
  curl -sS -F "file=@$SAMPLE" -F "language=en" -F "response_format=json" \
    http://127.0.0.1:8178/inference | head -50
  echo
fi

echo "==> Tail Vulkan init log:"
journalctl --user -u whisper-server -n 30 --no-pager | grep -iE 'vulkan|gpu|model|loading' | head -15 || true

echo
echo "    NEXT: bash 04-install-daemon.sh"
