#!/usr/bin/env bash
# One-time setup in a fresh container: TTS voice + python deps. Idempotent.
set -e
pip install -q piper-tts scipy faster-whisper 2>&1 | grep -v -i warning || true
V=~/voices; mkdir -p $V
for f in onnx onnx.json; do
  [ -s $V/ru_RU-ruslan-medium.$f ] || curl -sSL -o $V/ru_RU-ruslan-medium.$f "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium.$f"
done
echo "voice: $V/ru_RU-ruslan-medium.onnx"
