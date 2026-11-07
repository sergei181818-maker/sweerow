// Collect video links from TikTok /discover/ or /tag/ pages. Usage: node collect.js url1 url2 ... > urls.txt
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ locale: 'ru-RU', userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36' });
  const seen = new Set();
  for (const u of process.argv.slice(2)) {
    const p = await ctx.newPage();
    try {
      await p.goto(u, { waitUntil: 'domcontentloaded', timeout: 40000 }); await p.waitForTimeout(4000);
      for (let i = 0; i < 3; i++) { await p.mouse.wheel(0, 2500); await p.waitForTimeout(1500); }
      const links = await p.$$eval('a', as => as.map(a => a.href));
      const html = await p.content();
      (html.match(/https?:\\?\/\\?\/www\.tiktok\.com\\?\/@[\w.]+\\?\/video\\?\/\d+/g) || []).forEach(l => links.push(l.replace(/\\/g, '')));
      let n = 0; links.forEach(l => { const m = l.match(/https:\/\/www\.tiktok\.com\/@[\w.]+\/video\/\d+/); if (m && !seen.has(m[0])) { seen.add(m[0]); console.log(m[0]); n++; } });
      console.error(n, u.slice(0, 90));
    } catch (e) { console.error('fail', u.slice(0, 90)); }
    await p.close();
  }
  await b.close();
})();
