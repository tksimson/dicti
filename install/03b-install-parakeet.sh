#!/bin/bash
# Phase 3b: Parakeet TDT v3 speech-to-text server (the default engine) as a user service.
# Own venv (sherpa-onnx + numpy) so the daemon stays stdlib + requests.
# Run as your normal user (NOT sudo). Idempotent.

set -euo pipefail

if [[ $EUID -eq 0 ]]; then
  echo "Run as your normal user (without sudo)."
  exit 1
fi

REPO_ROOT="$(dirname "$(dirname "$(readlink -f "$0")")")"
OPT="$HOME/opt/parakeet"
MODEL=sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8
MODEL_URL="https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/$MODEL.tar.bz2"
UNIT_DIR="$HOME/.config/systemd/user"

mkdir -p "$OPT" "$UNIT_DIR"

if [[ ! -x "$OPT/venv/bin/python" ]]; then
  python3 -m venv "$OPT/venv"
fi
"$OPT/venv/bin/pip" install -q --upgrade "sherpa-onnx==1.13.8" "numpy>=1.26,<3"
echo "==> venv ready: $OPT/venv"

if [[ ! -f "$OPT/$MODEL/encoder.int8.onnx" ]]; then
  echo "==> Downloading Parakeet TDT v3 int8 (~490 MB)"
  curl -fL --progress-bar "$MODEL_URL" | tar xj -C "$OPT"
fi
echo "==> Model ready: $OPT/$MODEL"

sed "s|@SRC@|$REPO_ROOT/src|g" "$REPO_ROOT/systemd/parakeet-server.service" \
  > "$UNIT_DIR/parakeet-server.service"
echo "==> Installed $UNIT_DIR/parakeet-server.service"

systemctl --user daemon-reload
systemctl --user enable parakeet-server.service
systemctl --user restart parakeet-server.service

echo "==> Waiting for the model to load"
for _ in $(seq 1 30); do
  curl -sf -o /dev/null http://127.0.0.1:8179/ && break
  sleep 1
done

SAMPLE="$HOME/opt/whisper.cpp/samples/jfk.wav"  # 16 kHz mono, like dicti's recordings
if [[ -f "$SAMPLE" ]]; then
  echo "==> Smoke test (curl)"
  curl -sS -F "file=@$SAMPLE" -F "response_format=json" http://127.0.0.1:8179/inference
  echo
fi

echo
echo "    NEXT: bash 04-install-daemon.sh"
