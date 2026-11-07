# Piper TTS per line; words in {braces} are swears: voice.wav keeps them, voice_bleep.wav replaces them with a beep.
import json, subprocess, sys, wave, os, re, numpy as np
voice = sys.argv[1]; out = sys.argv[2] if len(sys.argv) > 2 else "build"
os.makedirs(out, exist_ok=True)
lines = json.load(open("script.json", encoding="utf-8"))
def synth(text, ls, p):
    subprocess.run(["piper", "-m", voice, "-f", p, "--length-scale", str(ls), "--sentence-silence", "0.1"], input=text.encode(), check=True, capture_output=True)
    w = wave.open(p); r = w.getframerate(); a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16); w.close()
    nz = np.where(np.abs(a) > 300)[0]
    return r, (a[max(0, nz[0] - int(.02 * r)):nz[-1] + int(.04 * r)] if len(nz) else a)
RATE = 22050; t = 0.3; timeline = []; clean = []; bleep = []
for i, ln in enumerate(lines):
    ls = ln.get("ls", 0.88)
    plain = ln["text"].replace("{", "").replace("}", "")
    RATE, c = synth(plain, ls, f"{out}/l{i:02d}.wav")
    b = c.copy()
    # beep over each swear: position estimated by character share (+25% padding)
    for m in re.finditer(r"\{([^}]+)\}", ln["text"]):
        pre = len(ln["text"][:m.start()].replace("{", "").replace("}", "")); L = len(plain)
        s0 = pre / L; s1 = (pre + len(m.group(1))) / L; pad = (s1 - s0) * 0.25
        a0, a1 = int(max(0, s0 - pad) * len(c)), int(min(1, s1 + pad) * len(c))
        tt = np.arange(a1 - a0) / RATE; b[a0:a1] = (np.sin(2 * np.pi * 1000 * tt) * 9000).astype(np.int16)
    if i > 0: t += 0.16 if lines[i - 1]["scene"] == ln["scene"] else 0.38
    timeline.append({**ln, "start": round(t, 3), "end": round(t + len(c) / RATE, 3)})
    clean.append((t, c)); bleep.append((t, b)); t += len(c) / RATE
total = t + 1.4
for name, segs in (("voice", clean), ("voice_bleep", bleep)):
    buf = np.zeros(int(total * RATE) + 1, dtype=np.int16)
    for st, a in segs: s = int(st * RATE); buf[s:s + len(a)] = a
    w = wave.open(f"{out}/{name}.wav", "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(buf.tobytes()); w.close()
json.dump({"duration": round(total, 3), "lines": timeline}, open(f"{out}/timeline.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("total", round(total, 2), "s")
