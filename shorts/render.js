// Renders template.html frame by frame with headless Chromium (several pages
// in parallel) and pipes the frames into ffmpeg together with the audio track.
// Usage: node render.js <timeline.json> <audio.wav> <out.mp4> [fps] [workers]
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");
const { once } = require("events");
const { chromium } = require("playwright");

(async () => {
  const [, , tlPath, audioPath, outPath, fpsArg, workersArg] = process.argv;
  const TL = JSON.parse(fs.readFileSync(tlPath, "utf8"));
  const fps = Number(fpsArg) || 30;
  const workers = Number(workersArg) || Math.max(1, os.cpus().length);
  const total = Math.ceil(TL.total * fps);
  const frames = new Array(total);
  const t0 = Date.now();

  const browser = await chromium.launch();
  let next = 0, done = 0;
  async function worker() {
    const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
    await page.addInitScript((tl) => { window.TL = tl; }, TL);
    await page.goto("file://" + path.join(__dirname, "template.html"));
    await page.waitForFunction(() => window.ready === true);
    while (next < total) {
      const i = next++;
      await page.evaluate((t) => window.seek(t), i / fps);
      frames[i] = await page.screenshot({ type: "jpeg", quality: 92 });
      if (++done % 150 === 0) process.stdout.write(`  кадр ${done}/${total}\n`);
    }
    await page.close();
  }
  await Promise.all(Array.from({ length: workers }, worker));
  await browser.close();

  const ff = spawn("ffmpeg", [
    "-y", "-loglevel", "error",
    "-f", "image2pipe", "-framerate", String(fps), "-c:v", "mjpeg", "-i", "-",
    "-i", audioPath,
    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
    outPath,
  ], { stdio: ["pipe", "inherit", "inherit"] });
  for (const buf of frames) if (!ff.stdin.write(buf)) await once(ff.stdin, "drain");
  ff.stdin.end();
  const [code] = await once(ff, "close");
  if (code !== 0) { console.error("ffmpeg завершился с ошибкой", code); process.exit(1); }
  console.log(`  готово: ${total} кадров за ${((Date.now() - t0) / 1000).toFixed(0)} с`);
})();
