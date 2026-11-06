const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  const html = require('fs').readFileSync(process.argv[2], 'utf8');
  await p.setContent('<!doctype html><html><head><meta charset="utf-8"></head><body>' + html + '</body></html>', { waitUntil: 'networkidle' });
  await p.waitForTimeout(300);
  const t = await p.evaluate(() => [...document.querySelectorAll('.plain')].map(d => {
    const s = d.closest('section'); const h = s && s.querySelector('h2');
    return '## ' + (h ? h.innerText : '') + '\n' + d.innerText.replace(/^IN PLAIN WORDS\s*/i, '');
  }).join('\n\n'));
  require('fs').writeFileSync(process.argv[3], t); await b.close();
})();
