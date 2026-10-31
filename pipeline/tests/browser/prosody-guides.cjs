/* Optional reader guides: collapsed, source-linked, responsive and usable without JS. */
const assert = require('node:assert/strict');
const puppeteer = require('puppeteer');
const base = (process.env.PROSODY_TEST_URL || 'http://localhost:8262/').replace(/\/?$/, '/');

(async () => {
  const browser = await puppeteer.launch({headless:'new', args:['--no-sandbox']});
  try {
    const page = await browser.newPage(), errors = [], engineRequests = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (/\/(?:chhanda|kavita-lekhan)\/(?:engine|app|metres)\.js/.test(request.url())) engineRequests.push(request.url());
    });
    async function go(id) {
      await page.goto(base + 'chhandas/' + id + '/', {waitUntil:'networkidle2'});
      await page.evaluate(() => document.fonts.ready);
    }
    async function noOverflow() {
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    }
    await page.setViewport({width:1280,height:1000});
    await go('shardul');
    assert.equal(await page.$eval('.metre-guide', el => el.open), false);
    assert.ok(await page.$eval('.metre-guide', el => el.getBoundingClientRect().height < 80));
    await page.screenshot({path:'/tmp/metre-guide-closed-desktop.png'});
    await page.focus('.metre-guide > summary');
    await page.keyboard.press('Enter');
    assert.equal(await page.$eval('.metre-guide', el => el.open), true);
    assert.match(await page.$eval('.metre-guide-body', el => el.textContent), /बाह्रौँ अक्षरपछि यति/);
    await noOverflow();
    await (await page.$('.metre-guide')).screenshot({path:'/tmp/metre-guide-shardul-desktop.png'});
    const example = await page.$eval('.metre-example a', a => a.href);
    await page.goto(example, {waitUntil:'networkidle2'});
    assert.match(new URL(page.url()).hash, /^#chhanda-/);
    assert.ok(await page.$('.ln:target'));

    // Every published category has a closed guide and an existing source passage.
    const coverage = await page.evaluate(async base => {
      const parse = text => new DOMParser().parseFromString(text, 'text/html');
      const index = parse(await (await fetch(base + 'chhandas/')).text());
      const links = Array.from(index.querySelectorAll('.shelf > a'), a => new URL(a.getAttribute('href'), base + 'chhandas/').href);
      return Promise.all(links.map(async url => {
        const doc = parse(await (await fetch(url)).text());
        const panel = doc.querySelector('details.metre-guide'), example = panel.querySelector('.metre-example a');
        const target = new URL(example.getAttribute('href'), url);
        const response = await fetch(target.href);
        const source = parse(await response.text());
        return !panel.open && panel.querySelector('summary').textContent === 'यस छन्दबारे र पढ्ने तरिका'
          && !!doc.querySelector('.prosody-filters') && response.ok
          && (!target.hash || !!source.getElementById(decodeURIComponent(target.hash.slice(1))));
      }));
    }, base);
    assert.equal(coverage.length, 32);
    assert.ok(coverage.every(Boolean));
    console.log('PASS: all 32 guides start closed and link to existing source passages');

    await page.setViewport({width:375,height:900});
    for (const id of ['shardul','giti','ramal_musamman_mahzuf','muktachhanda']) {
      await go(id);
      await noOverflow();
      assert.equal(await page.$eval('.metre-guide', el => el.open), false);
      await page.click('.metre-guide > summary');
      assert.equal(await page.$eval('.metre-guide', el => el.open), true);
      await noOverflow();
      if (id === 'muktachhanda') {
        assert.equal(await page.$('.metre-pattern'), null);
        assert.ok(await page.$('.prosody-write'));
      }
      await (await page.$('.metre-guide')).screenshot({path:'/tmp/metre-guide-' + id + '-mobile.png'});
    }
    await page.evaluate(() => document.documentElement.setAttribute('data-theme','dark'));
    await new Promise(resolve => setTimeout(resolve,350));
    await (await page.$('.metre-guide')).screenshot({path:'/tmp/metre-guide-mobile-dark.png'});
    assert.deepEqual(engineRequests, []);
    assert.deepEqual(errors, []);
    console.log('PASS: keyboard, mobile and dark-theme guides without writing-engine requests or browser errors');

    await page.setJavaScriptEnabled(false);
    await go('malini');
    await page.click('.metre-guide > summary');
    assert.equal(await page.$eval('.metre-guide', el => el.open), true);
    assert.ok(await page.$('.metre-guide .prosody-write'));
    await noOverflow();
    console.log('PASS: native guide opens and keeps its links available with JavaScript disabled');
  } finally {await browser.close();}
})().catch(error => {console.error(error);process.exitCode=1;});
