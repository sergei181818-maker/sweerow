#!/usr/bin/env python3
"""TikTok scout: fetch public video pages, compute views/followers ratio, pull subtitles.
Usage: python3 scout.py urls.txt out.json [--watch N]   (urls.txt: one TikTok video URL per line)
Prints a markdown table sorted by ratio (best "outlier" videos first).
--watch N: download top-N videos and save a 4x3 frame contact sheet per video to
research/data/frames/<id>.jpg (open them with Read to actually SEE animation/editing style)."""
import json, re, sys, time, os, subprocess, http.cookiejar, urllib.request, concurrent.futures as cf
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
def get(url, ref=None, opener=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9", **({"Referer": ref} if ref else {})})
    with (opener.open if opener else urllib.request.urlopen)(req, timeout=25) as r: return r.read().decode("utf-8", "replace"), r.geturl()
def watch(url, outdir="research/data/frames"):
    """Download the video (needs the page's cookies) and build a frame contact sheet."""
    os.makedirs(outdir, exist_ok=True)
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    html, _ = get(url, opener=op)
    it = json.loads(re.search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', html, re.S).group(1))["__DEFAULT_SCOPE__"]["webapp.video-detail"]["itemInfo"]["itemStruct"]
    src = it["video"].get("playAddr") or it["video"].get("downloadAddr")
    mp4 = f"{outdir}/{it['id']}.mp4"; jpg = f"{outdir}/{it['id']}.jpg"
    req = urllib.request.Request(src, headers={"User-Agent": UA, "Referer": "https://www.tiktok.com/", "Range": "bytes=0-"})
    open(mp4, "wb").write(op.open(req, timeout=90).read())
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4], capture_output=True, text=True).stdout or 30)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp4, "-vf", f"fps=12/{dur:.2f},scale=270:-2,tile=4x3", "-frames:v", "1", jpg], check=True)
    os.remove(mp4); return jpg
def subtitles(item):
    for s in (item.get("video", {}).get("subtitleInfos") or []):
        if s.get("LanguageCodeName", "").startswith(("rus", "ru")) or len(item["video"]["subtitleInfos"]) == 1:
            try:
                vtt, _ = get(s["Url"], "https://www.tiktok.com/")
                lines = [l for l in vtt.splitlines() if l and not re.match(r"^(WEBVTT|\d+$|[\d:.]+ --> )", l)]
                return " ".join(lines)
            except Exception: return ""
    return ""
def scout(url):
    try:
        html, final = get(url.strip())
        m = re.search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', html, re.S)
        it = json.loads(m.group(1))["__DEFAULT_SCOPE__"]["webapp.video-detail"]["itemInfo"]["itemStruct"]
        st, au = it["stats"], it.get("authorStats", {})
        plays, fol = int(st.get("playCount", 0)), int(au.get("followerCount", 0))
        return {"url": f"https://www.tiktok.com/@{it['author']['uniqueId']}/video/{it['id']}", "author": it["author"]["uniqueId"],
                "plays": plays, "followers": fol, "ratio": round(plays / max(fol, 100), 1), "likes": int(st.get("diggCount", 0)),
                "shares": int(st.get("shareCount", 0)), "saves": int(st.get("collectCount", 0) or 0), "duration": it["video"].get("duration"),
                "created": time.strftime("%Y-%m-%d", time.gmtime(int(it["createTime"]))), "desc": it.get("desc", ""), "transcript": subtitles(it)}
    except Exception as e:
        return {"url": url.strip(), "error": str(e)[:120]}
if __name__ == "__main__":
    urls = list(dict.fromkeys(u.strip().split("?")[0] for u in open(sys.argv[1]) if "/video/" in u))
    with cf.ThreadPoolExecutor(6) as ex: res = list(ex.map(scout, urls))
    ok = sorted([r for r in res if "error" not in r], key=lambda r: -r["ratio"])
    json.dump(ok, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"ok {len(ok)} / {len(urls)}\n\n| ratio | plays | followers | date | author | desc |\n|---|---|---|---|---|---|")
    if "--watch" in sys.argv:
        n = int(sys.argv[sys.argv.index("--watch") + 1])
        for r in ok[:n]:
            try: r["frames"] = watch(r["url"])
            except Exception as e: r["frames_error"] = str(e)[:100]
        json.dump(ok, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in ok: print(f"| {r['ratio']}x | {r['plays']:,} | {r['followers']:,} | {r['created']} | @{r['author']} | {r['desc'][:60].replace('|','/')} |")
