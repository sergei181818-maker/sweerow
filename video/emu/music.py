# Procedural score + SFX synced to build/events.json -> build/music.wav (44.1k stereo)
import json, sys, wave, numpy as np
d = sys.argv[1] if len(sys.argv) > 1 else 'build'
ev = json.load(open(f'{d}/events.json')); tl = json.load(open(f'{d}/timeline.json'))
SR = 44100; T = tl['duration']; N = int(T * SR) + SR
L = np.zeros(N); R = np.zeros(N)
t = np.arange(N) / SR
rs = np.random.default_rng(7)
def lp(x, a):  # one-pole lowpass, a in (0,1)
    from scipy.signal import lfilter
    return lfilter([a], [1, a - 1], x)
def scene_at(x):
    for s in ev['scenes']:
        if s['start'] <= x < s['end']: return s['id']
    return 'cta'
# ---- pad: Am - F - C - G (and darker Dm in twist) ----
n2f = lambda n: 440 * 2 ** ((n - 69) / 12)
prog = [[45, 57, 60, 64], [41, 53, 57, 60], [48, 55, 60, 64], [43, 55, 59, 62]]
seg = 4.0
pad = np.zeros(N)
for ci in range(int(T / seg) + 2):
    st = ci * seg; chord = prog[ci % 4]
    env = np.clip((t - st + 1.0) / 1.5, 0, 1) * np.clip((st + seg + 1.0 - t) / 1.5, 0, 1)
    m = env > 0
    if not m.any(): continue
    tt = t[m]; acc = np.zeros(m.sum())
    for n in chord:
        f = n2f(n)
        for det in (-0.12, 0, 0.11):
            ff = f * 2 ** (det / 12)
            for h in range(1, 6):
                acc += np.sin(2 * np.pi * ff * h * tt + h * det * 3) / (h ** 1.4)
    pad[m] += acc * env[m]
pad = lp(pad, 0.035) * 0.05
# tremolo-ish slow swell
pad *= 0.75 + 0.25 * np.sin(2 * np.pi * 0.11 * t)
# intensity by scene
inten = np.array([{'hook': .9, 'island': .8, 'order': .9, 'end45': .8, 'leaflets': .85, 'years': 1.1, 'alone': .7, 'twist': .35, 'suzuki': .8, 'command': .9, 'final': 1.25, 'cta': 1.0, 'class': .6, 'panic': 1.15, 'mom': 1.0, 'dad': 1.05, 'evac': 1.1, 'wave': 1.3, 'zero': .45, 'angel': 1.0}.get(scene_at(x), .85) for x in np.arange(0, N) [::441] / SR])
inten = np.repeat(inten, 441)[:N]; inten = lp(inten, 0.0005)
pad *= inten
# sub drone
pad += np.sin(2 * np.pi * n2f(33) * t) * 0.035 * inten
# ---- pulse: soft kick at 88 bpm, off during twist ----
def kick(at, gain):
    n = int(0.45 * SR); tt = np.arange(n) / SR
    f = 110 * np.exp(-tt * 22) + 45
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 7) * gain
    i = int(at * SR); e = min(N, i + n); L[i:e] += y[:e - i]; R[i:e] += y[:e - i]
beat = 60 / 88
for s in ev['scenes']:
    if s['id'] in ('hook', 'twist', 'cta'): continue
    g = {'years': .32, 'final': .3, 'command': .26}.get(s['id'], .18)
    x = s['start'] + 0.3
    while x < s['end'] - 0.1: kick(x, g); x += beat
L += pad; R += pad
# ---- SFX ----
def add(at, y, gain=1.0, pan=0.0):
    i = int(at * SR)
    if i < 0: y = y[-i:]; i = 0
    e = min(N, i + len(y)); y = y[:e - i] * gain
    L[i:e] += y * (1 - max(0, pan)); R[i:e] += y * (1 + min(0, pan))
def noise(n): return rs.standard_normal(n)
def boom(soft):
    n = int(1.6 * SR); tt = np.arange(n) / SR
    f = 70 * np.exp(-tt * 4) + 32
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 2.6)
    y += lp(noise(n), 0.08) * np.exp(-tt * 18) * 0.6
    return y * (0.35 if soft else 0.8)
def whoosh():
    n = int(0.5 * SR); tt = np.arange(n) / SR
    env = np.sin(np.pi * tt / 0.5) ** 2
    x = noise(n); out = np.zeros(n); a = 0.02 + 0.25 * env; y = 0.0
    for i in range(n): y += a[i] * (x[i] - y); out[i] = y
    return out * env * 0.5
def stamp():
    n = int(0.9 * SR); tt = np.arange(n) / SR
    y = lp(noise(n), 0.25) * np.exp(-tt * 30) * 1.0
    f = 90 * np.exp(-tt * 10) + 38
    y += np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 5) * 0.9
    return y
def tick():
    n = int(0.06 * SR); tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * 2400 * tt) + 0.5 * noise(n)) * np.exp(-tt * 120) * 0.22
def pop():
    n = int(0.15 * SR); tt = np.arange(n) / SR
    f = 700 + 900 * (tt / 0.15)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 30) * 0.3
def ding():
    n = int(1.4 * SR); tt = np.arange(n) / SR
    return sum(np.sin(2 * np.pi * f * tt) * a for f, a in ((1318, .5), (2637, .25), (3951, .12))) * np.exp(-tt * 4) * 0.45
W = whoosh()
for e in ev['events']:
    k = e['type']
    if k == 'boom': add(e['t'], boom(e.get('soft')))
    elif k == 'whoosh': add(e['t'] - 0.1, W, 1, -0.3)
    elif k == 'stamp': add(e['t'] + 0.12, stamp(), 1.0)
    elif k == 'tick': add(e['t'], tick(), 1, 0.2)
    elif k == 'pop': add(e['t'], pop())
    elif k == 'ding': add(e['t'], ding())
# fade out end
fo = np.clip((T - t) / 1.5, 0, 1); L *= fo; R *= fo
m = max(np.abs(L).max(), np.abs(R).max()); L /= m / 0.9; R /= m / 0.9
st = (np.stack([L, R], 1)[: int(T * SR)] * 32767).astype(np.int16)
w = wave.open(f'{d}/music.wav', 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes()); w.close()
print('music ok', T)
