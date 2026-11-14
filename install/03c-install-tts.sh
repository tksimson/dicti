#!/bin/bash
# Phase 3c: the offline voice for `dicti --speak-toggle` (highlighted text read aloud).
# Supertonic 3 (Supertone, OpenRAIL-M weights): one model, Polish + English, 10 preset
# voices, run by sherpa-onnx in the parakeet venv (03b), so no new Python dependency.
# sherpa-onnx ships it int8 only; its two big parts sound better in fp32, so those come
# from Supertone's own release, pinned and checksummed. ~500 MB download, ~400 MB on disk.
# Run as your normal user (NOT sudo). Idempotent.

set -euo pipefail

if [[ $EUID -eq 0 ]]; then
  echo "Run as your normal user (without sudo)."
  exit 1
fi

TTS="$HOME/opt/parakeet/tts"
DST="$TTS/supertonic-3"
SHERPA=sherpa-onnx-supertonic-3-tts-int8-2026-05-11
SHERPA_URL="https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/$SHERPA.tar.bz2"
HF="https://huggingface.co/Supertone/supertonic-3/resolve/3cadd1ee6394adea1bd021217a0e650ede09a323/onnx"

[[ -x "$HOME/opt/parakeet/venv/bin/python" ]] || { echo "Missing parakeet venv, run 03b-install-parakeet.sh first"; exit 1; }

if [[ ! -f "$DST/vocoder.onnx" ]]; then
  mkdir -p "$DST"
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  echo "==> Downloading Supertonic 3 (sherpa-onnx package, ~140 MB)"
  curl -fL --progress-bar "$SHERPA_URL" | tar xj -C "$TMP"
  # The small parts are not quantized in the int8 package: identical to fp32.
  cp "$TMP/$SHERPA"/{tts.json,unicode_indexer.bin,voice.bin,LICENSE} "$DST/"
  cp "$TMP/$SHERPA/duration_predictor.int8.onnx" "$DST/duration_predictor.onnx"
  cp "$TMP/$SHERPA/text_encoder.int8.onnx" "$DST/text_encoder.onnx"
  echo "==> Downloading the fp32 vector estimator and vocoder (~360 MB)"
  curl -fL --progress-bar -o "$TMP/vector_estimator.onnx" "$HF/vector_estimator.onnx"
  curl -fL --progress-bar -o "$TMP/vocoder.onnx" "$HF/vocoder.onnx"
  (cd "$TMP" && sha256sum -c --quiet - <<'EOF'
883ac868ea0275ef0e991524dc64f16b3c0376efd7c320af6b53f5b780d7c61c  vector_estimator.onnx
085de76dd8e8d5836d6ca66826601f615939218f90e519f70ee8a36ed2a4c4ba  vocoder.onnx
EOF
  )
  mv "$TMP/vector_estimator.onnx" "$TMP/vocoder.onnx" "$DST/"
fi
echo "==> Voice ready: $DST"

# Piper voices from earlier dicti versions are no longer used.
rm -rf "$TTS"/vits-piper-pl_PL-gosia-medium "$TTS"/vits-piper-en_US-amy-medium

echo
echo "    Highlight text anywhere, press AltGr+Copilot (bound in 06-bind-shortcuts.sh)."
echo "    Voice and speed: the dicti panel menu."
echo "    NEXT: bash 04-install-daemon.sh"
