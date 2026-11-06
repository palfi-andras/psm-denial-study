const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const b = await chromium.launch();
  const out = {};
  for (const page of ['report', 'brief']) {
    const html = fs.readFileSync(page + '.html', 'utf8');
    for (const [w, tag] of [[1200, 'desk'], [400, 'phone']]) for (const scheme of ['light', 'dark']) {
      const ctx = await b.newContext({ viewport: { width: w, height: 900 }, colorScheme: scheme, deviceScaleFactor: 1 });
      const p = await ctx.newPage(); const errs = [];
      p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
      await p.setContent('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>' + html + '</body></html>', { waitUntil: 'networkidle' });
      await p.waitForTimeout(400);
      const info = await p.evaluate(() => {
        const sw = document.documentElement.scrollWidth, cw = document.documentElement.clientWidth;
        const ids = new Set([...document.querySelectorAll('[id]')].map(e => e.id));
        const badAnchors = [...document.querySelectorAll('a[href^="#"]')].map(a => a.getAttribute('href').slice(1)).filter(h => h && !ids.has(h));
        const ext = [...document.querySelectorAll('a[href^="http"]')].map(a => a.href);
        const emptyB = [...document.querySelectorAll('b[id],span[id]')].filter(e => /^t-/.test(e.id) && !e.textContent.trim()).map(e => e.id);
        const wide = [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > cw + 1 && getComputedStyle(e).position !== 'fixed' && !e.closest('.tablewrap,.chart,svg')).slice(0, 8).map(e => e.tagName + '.' + e.className);
        return { overflow: sw > cw, sw, cw, badAnchors, ext: [...new Set(ext)], emptyB, wide, h: document.documentElement.scrollHeight };
      });
      const f = `shots/${page}_${tag}_${scheme}.png`;
      await p.screenshot({ path: f, fullPage: true });
      out[`${page}_${tag}_${scheme}`] = { ...info, errs };
      await ctx.close();
    }
  }
  console.log(JSON.stringify(out, null, 1));
  await b.close();
})();
