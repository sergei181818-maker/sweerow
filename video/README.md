# Видео-пайплайн: анимированные истории с озвучкой и субтитрами

Каждое видео — папка `video/<slug>/` со сценарием и сценами. Пример: `video/onoda/`.

| Файл | Что делает |
|---|---|
| `script.json` | реплики: `scene`, `text` (для озвучки, числа словами), `sub` (для субтитров), опц. `ls` — темп |
| `tts.py` | озвучка Piper (офлайн, русский голос) → `build/voice.wav` + `timeline.json` с таймингами |
| `render.html` | все сцены, анимация и субтитры по словам на Canvas, функция `render(t)` |
| `render.js` | покадровый рендер через Playwright → ffmpeg, 1080×1920 30 fps; `--preview t1,t2` — кадры для проверки |
| `music.py` | процедурная музыка + SFX (удары, тики, вжухи) по событиям из `events.json` |
| `mix.sh` | сведение голоса и музыки с дакингом, громкость -14 LUFS, итоговый mp4 |

## Запуск
```bash
pip install piper-tts scipy
mkdir -p ~/voices && cd ~/voices && for f in onnx onnx.json; do curl -sSLO "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium.$f"; done
cd video/onoda
python3 tts.py ~/voices/ru_RU-ruslan-medium.onnx build
node render.js build --preview 2,10,20     # проверить кадры
node render.js build && python3 music.py build && ./mix.sh build build/final.mp4
```
Проверка дикции: `faster-whisper` (модель small) на `build/voice.wav`.
