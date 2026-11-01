#!/usr/bin/env python3
"""Собирает вертикальный шортс «Что бы ты сделал?» из JSON-сценария.

Конвейер: сценарий -> озвучка (edge-tts, с таймингом каждого слова) ->
звуковые эффекты -> таймлайн -> покадровый рендер графики -> MP4 1080x1920.

    python3 shorts/make_short.py shorts/episodes/ep01_les.json
"""
import argparse
import asyncio
import hashlib
import json
import os
import ssl
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
SR = 44100


# ---------------------------------------------------------------- voice ----
def _setup_tts():
    import edge_tts.communicate as c

    # В облачной среде трафик идёт через прокси со своим сертификатом.
    ca = os.environ.get("TTS_CA_BUNDLE", "/root/.ccr/ca-bundle.crt")
    if os.path.exists(ca):
        c._SSL_CTX = ssl.create_default_context(cafile=ca)


async def tts(text, voice, rate, cache):
    import edge_tts

    key = hashlib.sha1(f"{voice}|{rate}|{text}".encode()).hexdigest()[:16]
    mp3, meta = cache / f"{key}.mp3", cache / f"{key}.json"
    if mp3.exists() and meta.exists():
        return mp3, json.loads(meta.read_text())
    words = []
    com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    tmp = mp3.with_suffix(".part")
    with open(tmp, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append({"t": ch["text"], "s": ch["offset"] / 1e7, "d": ch["duration"] / 1e7})
    tmp.replace(mp3)
    meta.write_text(json.dumps(words, ensure_ascii=False))
    return mp3, words


def decode(path):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
        capture_output=True, check=True,
    ).stdout
    a = np.frombuffer(raw, dtype=np.float32).copy()
    loud = np.nonzero(np.abs(a) > 0.01)[0]
    return a[: loud[-1] + int(0.05 * SR)] if len(loud) else a


# ------------------------------------------------------------------ sfx ----
def _t(sec):
    return np.arange(int(sec * SR)) / SR


def boom():
    t = _t(1.0)
    f = 70 * np.exp(-t * 3) + 38
    return 0.9 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 4.5) + \
        0.25 * np.random.default_rng(1).standard_normal(len(t)) * np.exp(-t * 18)


def whoosh(sec=0.4):
    t = _t(sec)
    n = np.random.default_rng(2).standard_normal(len(t))
    n = np.convolve(n, np.ones(6) / 6, mode="same")
    return 0.35 * n * np.sin(np.pi * t / sec) ** 2


def pop():
    t = _t(0.12)
    f = 950 - 450 * (t / 0.12)
    return 0.5 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 35)


def tick():
    t = _t(0.06)
    return 0.6 * np.sin(2 * np.pi * 1650 * t) * np.exp(-t * 70)


def heartbeat():
    t = _t(0.2)
    th = np.sin(2 * np.pi * 52 * t) * np.exp(-t * 22)
    out = np.zeros(int(0.45 * SR))
    out[: len(th)] += 0.9 * th
    out[int(0.22 * SR): int(0.22 * SR) + len(th)] += 0.6 * th
    return out


def buzzer():
    t = _t(0.45)
    return 0.22 * np.sign(np.sin(2 * np.pi * 180 * t)) * np.exp(-t * 6)


def ding():
    t = _t(1.2)
    return 0.3 * (np.sin(2 * np.pi * 1320 * t) + 0.6 * np.sin(2 * np.pi * 1980 * t)) * np.exp(-t * 4)


def drone(sec):
    t = _t(sec)
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 0.25 * t)
    wind = np.convolve(np.random.default_rng(3).standard_normal(len(t)), np.ones(200) / 200, mode="same")
    fade = np.minimum(1, t / 0.3) * np.minimum(1, (sec - t) / 1.0)
    return (0.05 * (np.sin(2 * np.pi * 55 * t) + 0.7 * np.sin(2 * np.pi * 82.4 * t)) * lfo + 0.5 * wind) * fade


def place(track, clip, at, gain=1.0):
    i = int(at * SR)
    j = min(len(track), i + len(clip))
    if i < len(track):
        track[i:j] += gain * clip[: j - i]


# --------------------------------------------------------------- build -----
def build_segments(ep):
    segs = [("hook", ep["hook"]["say"], 0.2, False)]
    segs += [(f"sit{i}", s["say"], 0.12, True) for i, s in enumerate(ep["situation"])]
    segs += [("question", ep["question"]["say"], 0.15, True)]
    segs += [(f"opt{i}", o["say"], 0.22, True) for i, o in enumerate(ep["options"])]
    segs += [("timer", ep["timer"]["say"], 0.1, True)]
    segs += [("cta", ep["cta"]["say"], 1.2, True)]
    return segs  # (id, text, gap_after, captions)


def find_word(words, prefix, default):
    for w in words:
        if w["t"].lower().startswith(prefix.lower()):
            return w["s"]
    return default


def caption_groups(seg_id, words, seg_start, seg_end, max_words=3):
    # Режем на группы до 3 слов и всегда начинаем новую группу после паузы
    # (конец фразы), чтобы субтитры не перескакивали через точку.
    chunks, cur = [], []
    for w in words:
        pause = cur and w["s"] - (cur[-1]["s"] + cur[-1]["d"]) > 0.18
        if cur and (len(cur) == max_words or pause):
            chunks.append(cur)
            cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    groups = []
    for chunk in chunks:
        groups.append({
            "seg": seg_id,
            "s": seg_start + chunk[0]["s"],
            "words": [{"t": w["t"].strip(".,!?…").upper(), "s": seg_start + w["s"]} for w in chunk],
            "last_end": seg_start + chunk[-1]["s"] + chunk[-1]["d"],
        })
    for a, b in zip(groups, groups[1:]):
        a["e"] = b["s"]
    if groups:
        groups[-1]["e"] = min(seg_end, groups[-1]["last_end"] + 0.35)
    return groups


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--fps", type=int, default=30)
    args = ap.parse_args()

    ep = json.loads(Path(args.episode).read_text())
    out = ROOT / "out" / ep["id"]
    cache = ROOT / ".cache"
    out.mkdir(parents=True, exist_ok=True)
    cache.mkdir(exist_ok=True)

    print("1/4 Озвучка…")
    _setup_tts()
    segs = build_segments(ep)
    results = []
    for _, text, _, _ in segs:  # по одному: сервис не любит параллельные запросы
        for attempt in range(10):
            try:
                results.append(await tts(text, ep["voice"], ep["rate"], cache))
                break
            except Exception as e:
                if attempt == 9:
                    raise RuntimeError(f"Не удалось озвучить: {text!r}") from e
                await asyncio.sleep(1.5)

    print("2/4 Таймлайн и звук…")
    cursor, seg_tl, voice_clips, groups, all_words = 0.0, {}, [], [], {}
    for (sid, _, gap, caps), (mp3, words) in zip(segs, results):
        audio = decode(mp3)
        dur = len(audio) / SR
        start = cursor
        seg_tl[sid] = {"s": round(start, 3), "e": round(start + dur, 3)}
        voice_clips.append((audio, start))
        all_words[sid] = words
        cursor = start + dur + gap
        if sid == "timer":
            n = ep["timer"]["seconds"]
            seg_tl[sid]["count_start"] = round(cursor, 3)
            seg_tl[sid]["count_end"] = round(cursor + n, 3)
            cursor += n + 0.25
        end = cursor if sid != "cta" else start + dur + gap
        if caps:
            groups += caption_groups(sid, words, start, end)
    total = cursor

    marks = {
        "dark": seg_tl["sit2"]["s"] + find_word(all_words["sit2"], "стемн", 0.5),
        "answer": seg_tl["cta"]["s"] + find_word(all_words["cta"], "правильн", 1.2),
        "subscribe": seg_tl["cta"]["s"] + find_word(all_words["cta"], "подпиш", 3.0),
    }

    n = int(total * SR) + SR
    voice = np.zeros(n, dtype=np.float64)
    for audio, at in voice_clips:
        place(voice, audio, at)
    sfx = np.zeros(n, dtype=np.float64)
    place(sfx, drone(total), 0, 1.0)
    place(sfx, boom(), 0, 0.9)
    for i in range(len(ep["situation"])):
        place(sfx, whoosh(), seg_tl[f"sit{i}"]["s"] - 0.15, 0.8)
    place(sfx, pop(), seg_tl["question"]["s"] - 0.03, 0.8)
    for i in range(len(ep["options"])):
        place(sfx, pop(), seg_tl[f"opt{i}"]["s"] - 0.03, 0.9)
    cs = seg_tl["timer"]["count_start"]
    for k in range(ep["timer"]["seconds"]):
        place(sfx, tick(), cs + k, 0.9)
        place(sfx, heartbeat(), cs + k + 0.05, 0.9)
    place(sfx, buzzer(), seg_tl["timer"]["count_end"], 1.0)
    place(sfx, whoosh(0.5), seg_tl["cta"]["s"] - 0.25, 0.9)
    place(sfx, ding(), marks["subscribe"], 0.8)

    mix = voice + sfx
    mix = mix[: int(total * SR)]
    mix *= 0.95 / max(1e-6, np.max(np.abs(mix)))
    wav_path = out / "audio.wav"
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype("<i2").tobytes())

    tl = {"total": round(total, 3), "episode": ep, "seg": seg_tl, "groups": groups, "marks": marks}
    tl_path = out / "timeline.json"
    tl_path.write_text(json.dumps(tl, ensure_ascii=False, indent=1))
    print(f"   длительность: {total:.1f} с")

    print("3/4 Рендер графики…")
    mp4 = out / f"{ep['id']}.mp4"
    subprocess.run(["node", str(ROOT / "render.js"), str(tl_path), str(wav_path), str(mp4), str(args.fps)], check=True)

    print("4/4 Текст для публикации…")
    post = ep.get("post", {})
    (out / "post.txt").write_text(
        f"НАЗВАНИЕ:\n{post.get('title', '')}\n\n"
        f"ОПИСАНИЕ:\n{post.get('description', '')}\n\n"
        f"ХЕШТЕГИ:\n{' '.join(post.get('hashtags', []))}\n\n"
        f"ЗАКРЕПЛЁННЫЙ КОММЕНТАРИЙ (через сутки):\n{ep.get('answer_for_pinned_comment', '')}\n"
    )
    print(f"Готово: {mp4}")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
