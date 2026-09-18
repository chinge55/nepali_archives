/* Integration regressions against the generated site and real Pagefind index.
 * Serve site/, install puppeteer, then run:
 * SEARCH_TEST_URL=http://localhost:8262/ node pipeline/tests/browser/search.cjs
 * Optional SEARCH_SCREENSHOTS writes desktop/mobile previews to that directory.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const puppeteer = require('puppeteer');
const base = process.env.SEARCH_TEST_URL || 'http://localhost:8262/';
const pause = ms => new Promise(r => setTimeout(r, ms));
let browser, count = 0;
async function input(p, value) {
  await p.$eval('#q', (el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles:true})); }, value);
}
async function settled(p) {
  await p.waitForFunction(() => {
    const ft = document.querySelector('#ft');
    return ft.textContent && !ft.textContent.includes('खोज्दै');
  }, {timeout:30000});
}
async function search(p, value) { await input(p, value); await settled(p); }
async function first(p) { return p.$eval('.ftlink', el => new URL(el.href).pathname); }
async function test(name, run, configure, route = '') {
  const context = await (browser.createBrowserContext ? browser.createBrowserContext() : browser.createIncognitoBrowserContext());
  const p = await context.newPage(), errors = [];
  p.on('pageerror', e => errors.push(e.message));
  try {
    if (configure) await configure(p);
    await p.goto(new URL(route, base).href, {waitUntil:'domcontentloaded'});
    await run(p);
    assert.deepEqual(errors, [], 'uncaught browser errors');
    console.log(`PASS ${++count}: ${name}`);
  } finally { await context.close(); }
}
const muna = '/authors/devkota/munamadan/';
(async () => {
  browser = await puppeteer.launch({headless:'new', args:['--no-sandbox']});
  await test('Roman, Nepali, mixed-script and alternate-spelling passages across authors', async p => {
    const examples = [
      ['saag ra sisnu', muna], ['sag ra sisnu', muna], ['साग र सिस्नु', muna],
      ['saag र sisnu', muna], ['  SAAG   RA   SISNU  ', muna], ['"saag ra sisnu"', muna],
      ['manis thulo dilale huncha', muna], ['मानिस ठूलो दिलले हुन्छ', muna],
      ['kun mandirma janchhau yatri', '/authors/devkota/yatri/'],
      ['कुन मन्दिरमा जान्छौ यात्री', '/authors/devkota/yatri/'],
      ['jarur sathi ma pagal', '/authors/devkota/pagal/'],
      ['म शब्दलाई देख्दछु', '/authors/devkota/pagal/'],
      ['बालक बबुरो द्विज शुकनामा', '/authors/lekhnath_paudyal/pijarako_suga/'],
      ['balak baburo dwij shukanama', '/authors/lekhnath_paudyal/pijarako_suga/'],
    ];
    for (const [query, expected] of examples) {
      await search(p, query); assert.equal(await first(p), expected, query);
      assert.ok(await p.$eval('.ftlink .ex mark', el => el.textContent.length > 2), query);
    }
    await search(p, 'muna madan');
    assert.equal(await p.$eval('#results a', el => new URL(el.href).pathname), muna);
  });
  await test('literal phrases and excerpts preserve vowel signs', async p => {
    await search(p, '"साग र सिस्नु"');
    assert.equal(await first(p), muna);
    assert.equal(await p.$eval('.ftlink mark', el => el.textContent), 'साग र सिस्नु');
    assert.equal(await p.$$eval('.ftlink', es => es.length), 1);
    await search(p, '"साग र सुस्नु"');
    assert.equal(await p.$$eval('.ftlink', es => es.length), 0);
    await search(p, '"साग र सिस्नु 123456789"');
    assert.equal(await p.$$eval('.ftlink', es => es.length), 0, 'numbers must not be dropped');
    await search(p, 'saag qwertyuiopasdf sisnu');
    assert.equal(await p.$$eval('.ftlink', es => es.length), 0, 'unknown words must not be dropped');
  });
  await test('passage link highlights the whole quote and scrolls there', async p => {
    await search(p, 'saag ra sisnu');
    await Promise.all([p.waitForNavigation(), p.click('.ftlink')]);
    await p.waitForSelector('mark.pagefind-highlight');
    await p.waitForFunction(() => {
      const y = document.querySelector('mark.pagefind-highlight').getBoundingClientRect().top;
      return y > 0 && y < innerHeight;
    });
    const mark = await p.$eval('mark.pagefind-highlight', el => ({text:el.textContent, y:el.getBoundingClientRect().top}));
    assert.equal(mark.text, 'साग र सिस्नु');
    assert.ok(mark.y > 0 && mark.y < 600, JSON.stringify(mark));
  });
  await test('phrase crossing verse lines stays searchable and highlights both lines', async p => {
    await search(p, '"जरूर साथी म पागल यस्तै छ मेरो हाल"');
    assert.equal(await first(p), '/authors/devkota/pagal/');
    await Promise.all([p.waitForNavigation(), p.click('.ftlink')]);
    await p.waitForSelector('mark.pagefind-highlight');
    const text = await p.$$eval('mark.pagefind-highlight', es => es.map(e => e.textContent).join(' '));
    assert.ok(text.includes('जरूर साथी म पागल'), text);
    assert.ok(text.includes('यस्तै छ मेरो हाल'), text);
  });
  await test('clearing before debounce does not resurrect results', async p => {
    await input(p, 'saag ra sisnu'); await input(p, ''); await pause(500);
    assert.equal(await p.$eval('#ft', el => el.textContent), '');
    assert.equal(await p.$eval('#results', el => el.textContent), '');
  });
  let held;
  async function heldRequest() {
    for (let n = 0; n < 1500; n++) { if (held) return; await pause(20); }
    throw Error('Timed out waiting for intercepted request');
  }
  await test('clearing during a pending search ignores its response', async p => {
    await input(p, 'saag ra sisnu');
    await heldRequest();
    await input(p, ''); await held.continue(); await pause(1200);
    assert.equal(await p.$eval('#ft', el => el.textContent), '');
  }, async p => {
    held = null; await p.setRequestInterception(true);
    p.on('request', r => /searchroman\/s\.json/.test(r.url()) ? held = r : r.continue());
  });
  await test('typing during title-index loading uses the latest query', async p => {
    await input(p, 'muna madan');
    await heldRequest();
    await input(p, 'yatri'); await held.continue();
    await p.waitForSelector('#results a');
    assert.equal(await p.$eval('#results a', el => new URL(el.href).pathname), '/authors/devkota/yatri/');
    await settled(p);
  }, async p => {
    held = null; await p.setRequestInterception(true);
    p.on('request', r => /search-index\.json/.test(r.url()) ? held = r : r.continue());
  });
  for (const asset of ['searchroman/s.json', 'pagefind/pagefind.js']) {
    let fail = true;
    await test(`failed ${asset} is visible and retry recovers`, async p => {
      await search(p, 'saag ra sisnu');
      await p.waitForSelector('.search-retry'); fail = false; await p.click('.search-retry');
      await settled(p); assert.equal(await first(p), muna);
    }, async p => {
      await p.setRequestInterception(true);
      p.on('request', r => fail && new URL(r.url()).pathname.endsWith(asset) ? r.respond({status:503, body:'Temporarily unavailable'}) : r.continue());
    });
  }
  await test('author scope keeps the matching work', async p => {
    await search(p, 'saag ra sisnu'); assert.equal(await first(p), muna);
    assert.ok((await p.$$eval('.ftlink', es => es.map(e => new URL(e.href).pathname))).every(u => u.startsWith('/authors/devkota/')));
  }, null, 'authors/devkota/');
  await test('another author scope excludes the work', async p => {
    await search(p, '"saag ra sisnu"'); assert.equal(await p.$$eval('.ftlink', es => es.length), 0);
  }, null, 'authors/lekhnath_paudyal/');
  await test('search deep links and mobile layout', async p => {
    await settled(p); assert.equal(await first(p), muna);
    const dir = process.env.SEARCH_SCREENSHOTS;
    if (dir) { fs.mkdirSync(dir, {recursive:true}); await p.screenshot({path:path.join(dir,'search-desktop.png'),fullPage:true}); }
    await p.setViewport({width:390,height:844});
    assert.ok(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'horizontal overflow');
    if (dir) await p.screenshot({path:path.join(dir,'search-mobile.png'),fullPage:true});
  }, null, '?q=saag+ra+sisnu');
  console.log(`${count} search integration scenarios passed.`);
})().catch(e => {console.error(e);process.exitCode=1;}).finally(async () => {if(browser)await browser.close();});
