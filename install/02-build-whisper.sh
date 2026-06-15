#!/bin/bash
# Phase 2: Clone and build whisper.cpp with Vulkan + CPU fallback.
# Downloads and quantizes the medium multilingual model.
# Run as the regular user (NOT sudo). Idempotent: skips clone/download/build if up to date.

set -euo pipefail

if [[ $EUID -eq 0 ]]; then
  echo "Run as your normal user (without sudo)."
  exit 1
fi

REPO_DIR="$HOME/opt/whisper.cpp"
MODEL_BASE="ggml-medium.bin"
MODEL_QUANT="ggml-medium-q5_0.bin"
VAD_MODEL="ggml-silero-v5.1.2.bin"   # silero VAD; streaming runs whisper-server with --vad

mkdir -p "$HOME/opt"

if [[ ! -d "$REPO_DIR/.git" ]]; then
  echo "==> Cloning whisper.cpp"
  git clone https://github.com/ggerganov/whisper.cpp "$REPO_DIR"
else
  echo "==> Updating whisper.cpp"
  git -C "$REPO_DIR" pull --ff-only
fi

cd "$REPO_DIR"

NPROC=$(nproc)

echo "==> Building Vulkan backend (build/)"
cmake -B build \
  -DGGML_VULKAN=ON \
  -DWHISPER_BUILD_SERVER=ON \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$NPROC"

echo "==> Building CPU fallback (build-cpu/)"
cmake -B build-cpu \
  -DGGML_VULKAN=OFF \
  -DWHISPER_BUILD_SERVER=ON \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build-cpu -j"$NPROC"

echo "==> Verifying both binaries"
ls -lh build/bin/whisper-cli build/bin/whisper-server build-cpu/bin/whisper-cli build-cpu/bin/whisper-server || true

echo "==> Fetching $MODEL_BASE if missing (~1.5GB download)"
if [[ ! -f "models/$MODEL_BASE" ]]; then
  bash ./models/download-ggml-model.sh medium
else
  echo "    already present"
fi

echo "==> Quantizing to $MODEL_QUANT (q5_0) if missing"
if [[ ! -f "models/$MODEL_QUANT" ]]; then
  # whisper.cpp renamed `quantize` -> `whisper-quantize` somewhere along the line
  ./build/bin/whisper-quantize "models/$MODEL_BASE" "models/$MODEL_QUANT" q5_0
else
  echo "    already present"
fi

echo "==> Fetching VAD model $VAD_MODEL if missing (silero, ~0.9MB)"
if [[ ! -f "models/$VAD_MODEL" ]]; then
  bash ./models/download-vad-model.sh silero-v5.1.2
else
  echo "    already present"
fi

ls -lh models/ggml-medium* "models/$VAD_MODEL"

echo
echo "==> Smoke test: Vulkan whisper-cli on bundled JFK sample"
./build/bin/whisper-cli -m "models/$MODEL_QUANT" -f samples/jfk.wav -l en 2>&1 | tail -20

echo
echo "==> If you saw 'Vulkan0:' / 'using Vulkan' in the log above, GPU path works."
echo "    NEXT: bash 03-install-whisper-server.sh"
echo
echo "    Optional Polish sanity check:"
echo "      pw-record -r 16000 --format=s16 --channels=1 /tmp/pl.wav   # Ctrl+C to stop after 10s of Polish"
echo "      $REPO_DIR/build/bin/whisper-cli -m $REPO_DIR/models/$MODEL_QUANT -f /tmp/pl.wav -l pl"
