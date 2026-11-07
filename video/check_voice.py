# Transcribe voice.wav with whisper-small to catch mispronounced lines. Usage: python3 check_voice.py build/voice.wav
import sys, wave, numpy as np
from scipy.signal import resample_poly
from faster_whisper import WhisperModel
w = wave.open(sys.argv[1]); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
a = resample_poly(a, 160, int(w.getframerate() / 100)).astype(np.float32)
for s in WhisperModel("small", device="cpu", compute_type="int8").transcribe(a, language="ru", beam_size=3)[0]:
    print(f"{s.start:5.1f} {s.text}")
