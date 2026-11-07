#!/usr/bin/env bash
# One-time setup in a fresh container: TTS voice + python deps. Idempotent.
set -e
pip install -q piper-tts scipy faster-whisper 2>&1 | grep -v -i warning || true
V=~/voices; mkdir -p $V
for f in onnx onnx.json; do
  [ -s $V/ru_RU-ruslan-medium.$f ] || curl -sSL -o $V/ru_RU-ruslan-medium.$f "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium.$f"
done
echo "voice: $V/ru_RU-ruslan-medium.onnx"
# Vosk TTS (better Russian voice, ONNX)
pip install -q vosk-tts 2>&1 | grep -v -i warning || true
[ -d $V/vosk-model-tts-ru-0.9-multi ] || (curl -sSL -o /tmp/vtts.zip https://alphacephei.com/vosk/models/vosk-model-tts-ru-0.9-multi.zip && unzip -q -o /tmp/vtts.zip -d $V && rm /tmp/vtts.zip)
echo "vosk: $V/vosk-model-tts-ru-0.9-multi"
