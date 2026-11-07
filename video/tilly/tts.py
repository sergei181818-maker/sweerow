# Synthesize each line with Piper, build voice.wav + timeline.json
import json, subprocess, sys, wave, os
voice = sys.argv[1]; out = sys.argv[2] if len(sys.argv) > 2 else "build"
os.makedirs(out, exist_ok=True)
lines = json.load(open("script.json", encoding="utf-8"))
RATE = None; t = 0.35; timeline = []; frames = []
GAP_SAME, GAP_SCENE = 0.18, 0.45
for i, ln in enumerate(lines):
    p = f"{out}/l{i:02d}.wav"
    subprocess.run(["piper", "-m", voice, "-f", p, "--length-scale", str(ln.get("ls", 0.9)), "--sentence-silence", "0.12"],
                   input=ln["text"].encode(), check=True, capture_output=True)
    w = wave.open(p); RATE = w.getframerate(); data = w.readframes(w.getnframes()); w.close()
    # trim trailing/leading silence lightly
    import numpy as np
    a = np.frombuffer(data, dtype=np.int16)
    nz = np.where(np.abs(a) > 300)[0]
    a = a[max(0, nz[0]-int(.03*RATE)):nz[-1]+int(.06*RATE)]
    dur = len(a) / RATE
    if i > 0:
        gap = GAP_SAME if lines[i-1]["scene"] == ln["scene"] else GAP_SCENE
        t += gap
    timeline.append({**ln, "start": round(t, 3), "end": round(t + dur, 3)})
    frames.append((t, a)); t += dur
total = t + 1.6
import numpy as np
buf = np.zeros(int(total * RATE) + 1, dtype=np.int16)
for st, a in frames:
    s = int(st * RATE); buf[s:s+len(a)] = a
w = wave.open(f"{out}/voice.wav", "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(buf.tobytes()); w.close()
json.dump({"duration": round(total, 3), "lines": timeline}, open(f"{out}/timeline.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("total", round(total, 2), "s")
