// Usage: node render.js build [--preview t1,t2,...]
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path'), { spawn } = require('child_process');
(async () => {
  const dir = process.argv[2] || 'build';
  const prevIdx = process.argv.indexOf('--preview');
  const timeline = JSON.parse(fs.readFileSync(path.join(dir, 'timeline.json'), 'utf8'));
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  page.on('pageerror', e => { console.error('PAGE ERROR', e); process.exit(1); });
  await page.goto('file://' + path.resolve(__dirname, 'render.html'));
  await page.evaluate(async () => { await Promise.all(['900 96px Inter', '800 50px Inter', '700 40px Inter', '600 30px Inter', '500 40px JetBrains Mono', '900 50px DejaVu Serif', '900 96px "Inter Display"', '800 60px "Inter Display"'].map(f => document.fonts.load(f, 'АБВ'))); });
  const info = await page.evaluate(tl => setup(tl), timeline);
  fs.writeFileSync(path.join(dir, 'events.json'), JSON.stringify(info, null, 1));
  const grab = async (t, f, q) => {
    const b64 = await page.evaluate(([t, f, q]) => { render(t, f); return document.getElementById('c').toDataURL('image/jpeg', q).split(',')[1]; }, [t, f, q]);
    return Buffer.from(b64, 'base64');
  };
  if (prevIdx > 0) {
    const ts = process.argv[prevIdx + 1].split(',').map(Number);
    fs.mkdirSync(path.join(dir, 'preview'), { recursive: true });
    for (const t of ts) fs.writeFileSync(path.join(dir, 'preview', `t${t.toFixed(1)}.jpg`), await grab(t, Math.round(t * 30), 0.8));
    console.log('previews', ts.length); await browser.close(); return;
  }
  const fps = 30, n = Math.ceil(timeline.duration * fps);
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-maxrate', '12M', '-bufsize', '24M', '-pix_fmt', 'yuv420p', path.join(dir, 'video_noaudio.mp4')], { stdio: ['pipe', 'inherit', 'inherit'] });
  const t0 = Date.now();
  for (let f = 0; f < n; f++) {
    const buf = await grab(f / fps, f, 0.94);
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (f % 300 === 0) console.log(`frame ${f}/${n} ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
  ff.stdin.end(); await new Promise(r => ff.on('close', r));
  console.log('done', n, 'frames in', ((Date.now() - t0) / 1000).toFixed(0), 's');
  await browser.close();
})();
