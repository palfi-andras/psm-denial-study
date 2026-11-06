// Dump the rendered visible text of a built page (after its scripts run). Usage: node rtext.js page.html out.txt
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1200, height: 900 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  const html = require('fs').readFileSync(process.argv[2], 'utf8');
  await p.setContent('<!doctype html><html><head><meta charset="utf-8"></head><body>' + html + '</body></html>', { waitUntil: 'networkidle' });
  await p.waitForTimeout(300);
  await p.evaluate(() => document.querySelectorAll('details').forEach(d => d.open = true));
  const t = await p.evaluate(() => document.body.innerText);
  require('fs').writeFileSync(process.argv[3], t);
  if (errs.length) console.log('ERRORS', errs);
  await b.close();
})();
