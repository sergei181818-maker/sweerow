# Vosk TTS, several voices. v: nar (narrator), me (your own voice in a voice message: phone filter), mom (from corridor: muffled + room echo)
# {word} = swear: voice.wav keeps it, voice_bleep.wav beeps it (position estimated by characters).
import json, sys, wave, os, re, numpy as np
from scipy.signal import butter, lfilter
from vosk_tts import Model, Synth
model = sys.argv[1]; out = sys.argv[2] if len(sys.argv) > 2 else "build"; os.makedirs(out, exist_ok=True)
SPK = {"nar": 4, "me": 3, "mom": 0, "creep": 0, "near": 3}
synth = Synth(Model(model_path=model)); lines = json.load(open("script.json", encoding="utf-8"))
def fx(a, r, kind):
    x = a.astype(np.float32) / 32768
    if kind == "me":
        b, c = butter(4, [320 / (r / 2), 3300 / (r / 2)], "band"); x = lfilter(b, c, x)
        x = np.tanh(x * 2.2) * 0.55; x += np.random.default_rng(1).standard_normal(len(x)) * 0.004
    if kind == "mom":
        b, c = butter(3, 1800 / (r / 2)); x = lfilter(b, c, x) * 0.8
        d = int(0.09 * r); y = x.copy(); y[d:] += x[:-d] * 0.35; y[2 * d:] += x[:-2 * d] * 0.18; x = y
    if kind == "creep":  # mom voice pitched down + slowed, close and dry with a long tail
        from scipy.signal import resample
        x = resample(x, int(len(x) * 1.18)) * 0.9
        d = int(0.13 * r); y = x.copy(); y[d:] += x[:-d] * 0.3; y[2 * d:] += x[:-2 * d] * 0.15; x = y
        x *= 0.85 + 0.15 * np.sin(np.arange(len(x)) / r * 2 * np.pi * 5)
    if kind == "near":  # your own voice, whisper-close: thin, slightly slowed
        from scipy.signal import resample
        b, c = butter(2, 500 / (r / 2), "high"); x = lfilter(b, c, x); x = resample(x, int(len(x) * 1.06)) * 0.75
    return (np.clip(x, -1, 1) * 32767).astype(np.int16)
RATE = 22050; t = 0.3; tl = []; clean = []; bleep = []
for i, ln in enumerate(lines):
    if "pause" in ln:  # silent beat (no voice), still its own scene
        tl.append({**ln, "text": "", "sub": "", "start": round(t, 3), "end": round(t + ln["pause"], 3)}); t += ln["pause"]; continue
    plain = ln["text"].replace("{", "").replace("}", "")
    p = f"{out}/l{i:02d}.wav"; synth.synth(plain, p, speaker_id=SPK[ln["v"]], speech_rate=ln.get("rate", 1.08))
    w = wave.open(p); RATE = w.getframerate(); a = np.frombuffer(w.readframes(w.getnframes()), np.int16); w.close()
    nz = np.where(np.abs(a) > 300)[0]; a = a[max(0, nz[0] - int(.02 * RATE)):nz[-1] + int(.05 * RATE)]
    c = fx(a, RATE, ln["v"]); b = c.copy()
    for m in re.finditer(r"\{([^}]+)\}", ln["text"]):
        pre = len(ln["text"][:m.start()].replace("{", "").replace("}", "")); L = len(plain)
        s0, s1 = pre / L, (pre + len(m.group(1))) / L; pad = (s1 - s0) * 0.25
        a0, a1 = int(max(0, s0 - pad) * len(c)), int(min(1, s1 + pad) * len(c))
        b[a0:a1] = (np.sin(2 * np.pi * 1000 * np.arange(a1 - a0) / RATE) * 9000).astype(np.int16)
    if i > 0 and "pause" not in lines[i - 1]: t += 0.14 if lines[i - 1]["scene"] == ln["scene"] else 0.34
    tl.append({**ln, "start": round(t, 3), "end": round(t + len(c) / RATE, 3)}); clean.append((t, c)); bleep.append((t, b)); t += len(c) / RATE + ln.get("pause_after", 0)
total = t + 1.4
for name, segs in (("voice", clean), ("voice_bleep", bleep)):
    buf = np.zeros(int(total * RATE) + 1, np.int16)
    for st, a in segs: s = int(st * RATE); buf[s:s + len(a)] = a
    w = wave.open(f"{out}/{name}.wav", "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(buf.tobytes()); w.close()
json.dump({"duration": round(total, 3), "lines": tl}, open(f"{out}/timeline.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("total", round(total, 2))
