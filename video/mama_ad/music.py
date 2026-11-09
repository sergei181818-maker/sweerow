# Ad score: ambient intro -> riser -> drop (4-on-floor, bass, chords, hats) -> soft outro. Synced to events.json.
import json, sys, wave, numpy as np
from scipy.signal import butter, lfilter
d = sys.argv[1] if len(sys.argv) > 1 else 'build'
ev = json.load(open(f'{d}/events.json')); SR = 44100; T = ev['duration']; N = int(T * SR) + SR
BPM = ev['bpm']; B = 60 / BPM; t = np.arange(N) / SR; rs = np.random.default_rng(3)
L = np.zeros(N); R = np.zeros(N)
E = {e['type']: e for e in ev['events'] if e['type'] in ('drop', 'outro', 'riser')}
drop, outro = E['drop']['t'], E['outro']['t']
n2f = lambda n: 440 * 2 ** ((n - 69) / 12)
def lp(x, f): b, a = butter(2, f / (SR / 2)); return lfilter(b, a, x)
def hp(x, f): b, a = butter(2, f / (SR / 2), 'high'); return lfilter(b, a, x)
def add(at, y, g=1.0, pan=0.0):
    i = int(at * SR); e = min(N, i + len(y)); y = y[:e - i] * g
    L[i:e] += y * (1 - max(0, pan)); R[i:e] += y * (1 + min(0, pan))
# chords: F - Am - G - C  (warm, uplifting), 2 bars each
prog = [[53, 57, 60, 64], [57, 60, 64, 67], [55, 59, 62, 67], [48, 55, 60, 64]]
bar = 4 * B
pad = np.zeros(N)
for ci in range(int(T / (2 * bar)) + 2):
    st = ci * 2 * bar; ch = prog[ci % 4]
    m = (t >= st - 0.3) & (t < st + 2 * bar + 0.6)
    if not m.any(): continue
    tt = t[m] - st; env = np.clip((tt + 0.3) / 0.6, 0, 1) * np.clip((2 * bar + 0.6 - tt) / 0.6, 0, 1)
    acc = sum(np.sin(2 * np.pi * n2f(n) * (1 + dt) * t[m]) for n in ch for dt in (-0.002, 0.002)) / 8
    pad[m] += acc * env
pad = lp(pad, 2500) * 0.22
pad *= np.where(t < drop, 0.7, np.where(t < outro, 0.55, 2.2))
L += pad; R += pad
# drums + bass between drop and outro
def kick():
    n = int(0.35 * SR); tt = np.arange(n) / SR; f = 120 * np.exp(-tt * 30) + 48
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 8)
def hat(): n = int(0.05 * SR); return hp(rs.standard_normal(n), 7000) * np.exp(-np.arange(n) / SR * 90) * 0.5
def clap(): n = int(0.2 * SR); return lp(hp(rs.standard_normal(n), 1200), 5000) * np.exp(-np.arange(n) / SR * 22) * 0.6
K, Hh, Cl = kick(), hat(), clap()
x = drop
while x < outro - 0.01:
    bi = round((x - drop) / B)
    add(x, K, 0.9)
    add(x + B / 2, Hh, 0.35, 0.3)
    if bi % 2 == 1: add(x, Cl, 0.45, -0.2)
    ci = int(x // (2 * bar)) % 4; root = prog[ci][0] - 24
    n = int(B * SR * 0.9); tt = np.arange(n) / SR
    bass = np.sin(2 * np.pi * n2f(root) * tt) + 0.3 * np.sin(2 * np.pi * n2f(root + 12) * tt)
    add(x + B * 0.5, bass * np.exp(-tt * 4) * 0.35)
    x += B
# arp sparkle all along
for k in range(int(T / (B / 2))):
    st = k * B / 2; ci = int(st // (2 * bar)) % 4; n = prog[ci][k % 4] + 12; nn = int(0.3 * SR); tt = np.arange(nn) / SR
    add(st, np.sin(2 * np.pi * n2f(n) * tt) * np.exp(-tt * 9) * (0.05 if st < drop else 0.07), 1, 0.4 if k % 2 else -0.4)
# fx
for e in ev['events']:
    ty = e['type']
    if ty == 'riser':
        n = int(e['dur'] * SR); tt = np.arange(n) / SR; p = tt / e['dur']
        y = hp(rs.standard_normal(n), 1500) * p ** 2 * 0.25 + np.sin(2 * np.pi * np.cumsum(200 + 1200 * p ** 2) / SR) * p ** 2 * 0.08
        add(e['t'], y)
    elif ty == 'impact':
        n = int(1.2 * SR); tt = np.arange(n) / SR; f = 70 * np.exp(-tt * 5) + 35
        add(e['t'], np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 3.5) * 0.8 + lp(rs.standard_normal(n), 3000) * np.exp(-tt * 12) * 0.25)
    elif ty == 'whoosh':
        n = int(0.45 * SR); tt = np.arange(n) / SR; env = np.sin(np.pi * tt / 0.45) ** 2
        add(e['t'], lp(rs.standard_normal(n), 2500) * env * 0.18, 1, 0.3)
    elif ty == 'click':
        n = int(0.04 * SR); tt = np.arange(n) / SR; add(e['t'], np.sin(2 * np.pi * 1800 * tt) * np.exp(-tt * 120) * 0.35)
fo = np.clip((T - t) / 2.0, 0, 1); L *= fo; R *= fo
m = max(np.abs(L).max(), np.abs(R).max()); L /= m / 0.9; R /= m / 0.9
w = wave.open(f'{d}/music.wav', 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((np.stack([L, R], 1)[:int(T * SR)] * 32767).astype(np.int16).tobytes()); w.close(); print('ok')
