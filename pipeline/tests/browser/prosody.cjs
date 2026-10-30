/* Exercise reviewed tags, scoped search, passage links and safe writer presets. */
const assert = require('node:assert/strict');
const puppeteer = require('puppeteer');
const base = (process.env.PROSODY_TEST_URL || 'http://localhost:8262/').replace(/\/?$/, '/');
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

(async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
  const context = await browser.createIncognitoBrowserContext();
  const page = await context.newPage(), errors = [], requests = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => requests.push(request.url()));
  async function go(route) { await page.goto(base + route, { waitUntil: 'networkidle0' }); }
  async function waitForPassage() {
    await page.waitForFunction(() => {
      const target = document.querySelector('.ln:target');
      if (!target) return false;
      const top = target.getBoundingClientRect().top, now = performance.now();
      const previous = window.__prosodyScrollWait;
      if (!previous || previous.id !== target.id || Math.abs(previous.top - top) > 0.5) {
        window.__prosodyScrollWait = { id: target.id, top, since: now };
        return false;
      }
      // Finish smooth scrolling before navigating to another hash in the same document.
      return top >= 0 && top < innerHeight && now - previous.since >= 200;
    });
  }
  try {
    await page.setViewport({ width: 1152, height: 1000 });
    await go('chhandas/');
    assert.match(await page.$eval('h1', n => n.textContent), /छन्दअनुसार/);
    assert.match(await page.$eval('.lead', n => n.textContent), /कृतिको छन्द पहिचान समीक्षा गरिएको छ/);
    assert.ok(await page.$$eval('.shelf > a', n => n.length) >= 20);
    await page.screenshot({ path: '/tmp/prosody-browse-desktop.png', fullPage: true });
    await go('authors/lekhnath_paudyal/radhakrishna/');
    assert.match(await page.$eval('.meta', n => n.textContent), /छन्द: मालिनी/);
    assert.equal(requests.some(url => /\/chhanda\/(?:engine|app|metres)\.js/.test(url)), false, 'reader pages must not load the writing engine');
    await page.screenshot({ path: '/tmp/prosody-reader-tag.png', fullPage: true });
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle0' }), page.click('.meta a[href*="chhandas/"]')]);
    assert.match(await page.$eval('h1', n => n.textContent), /मालिनी छन्दका कविता/);
    await page.select('#metre-author', 'लेखनाथ पौड्याल');
    assert.equal(await page.$$eval('.group', nodes => nodes.filter(n => getComputedStyle(n).display !== 'none').length), 1);
    await page.type('#q', 'विषय');
    await page.waitForSelector('#ft .ftlink');
    const results = await page.$$eval('#ft .ftlink', nodes => nodes.map(n => n.href));
    assert.ok(results.some(url => url.includes('/authors/lekhnath_paudyal/radhakrishna/')));
    assert.ok(results.every(url => url.includes('/authors/lekhnath_paudyal/')));
    console.log('PASS: reviewed tags, author filtering and metre-scoped full-text search');

    await go('chhandas/malini/');
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle0' }), page.click('.prosody-passages a[href*="/shakuntala/"]')]);
    assert.match(new URL(page.url()).hash, /^#chhanda-/);
    assert.ok(await page.$eval('.ln:target', n => n.textContent.includes('विपिन')));
    assert.match(await page.$eval('.prosody-section', n => n.textContent), /यस खण्डका अंश/);
    assert.match(await page.$eval('h1', n => n.textContent), /द्वितीय सर्ग/);
    await page.screenshot({ path: '/tmp/prosody-passage.png', fullPage: false });
    console.log('PASS: mixed works link directly to the correct text passage');

    await go('chhandas/upajati/');
    assert.match(await page.$eval('h1', n => n.textContent), /उपजाति छन्दका कविता/);
    assert.equal(await page.$('.prosody-write'), null);
    await page.screenshot({ path: '/tmp/prosody-upajati-desktop.png', fullPage: true });
    await go('authors/bhanubhakta_acharya/katai_kharani_chhari_bhus_katai/');
    assert.match(await page.$eval('.meta', n => n.textContent), /छन्द: उपजाति/);
    await go('authors/bhimnidhi_tiwari/sharachchandra/');
    assert.match(await page.$eval('.meta', n => n.textContent), /छन्द: वंशस्थ/);
    await go('authors/bhanubhakta_acharya/n_mrityu_tarnya_ho_yasari/');
    assert.equal(await page.$('.meta a[href*="chhandas/"]'), null, 'uncertain readings must not publish a tag');
    await go('authors/bhanubhakta_acharya/balaji/');
    assert.equal(await page.$eval('#chhanda-details', n => n.open), false);
    await page.click('#chhanda-details summary');
    assert.equal(await page.$$eval('#chhanda-details li', n => n.length), 2);
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle0' }), page.click('#chhanda-details a[href*="#chhanda-vasanta-2"]')]);
    assert.match(await page.$eval('.ln:target', n => n.textContent), /याँहाँ बसेर कविता/);
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle0' }), page.click('#chhanda-details a[href*="#chhanda-malini-1"]')]);
    assert.match(await page.$eval('.ln:target', n => n.textContent), /यति दिन पछि मैले/);
    console.log('PASS: new metre families, uncertain exclusions and both Balaji stanza links');

    await go('chhandas/anushtup/');
    assert.match(await page.$eval('h1', n => n.textContent), /अनुष्टुप् छन्दका कविता/);
    assert.equal(await page.$('.prosody-write'), null);
    await page.screenshot({ path: '/tmp/prosody-anushtup-desktop.png', fullPage: true });
    await page.type('#q', 'सानू');
    await page.waitForSelector('#ft .ftlink[href*="/manoladdu/"]');
    const mixedCases = [
      ['jagannath_upadhyay_guraganyin/bairagya_ba_santosh', ['shikharini-example', 'shardul-ending']],
      ['lekhnath_paudyal/manoladdu', ['swagata-2', 'anushtup-21']],
      ['bhanubhakta_acharya/badhushiksha', ['shardul-21', 'malini-27']],
      ['bhanubhakta_acharya/prashnottaramala', ['upajati-1', 'vasanta-36', 'upajati-48']],
    ];
    for (const [route, ids] of mixedCases) {
      await go('authors/' + route + '/');
      assert.match(await page.$eval('.meta', n => n.textContent), /छन्द: मिश्रित/);
      assert.equal(await page.$eval('#chhanda-details', n => n.open), false);
      await page.click('#chhanda-details summary');
      assert.equal(await page.$$eval('#chhanda-details li', n => n.length), ids.length);
      for (const id of ids) {
        await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle0' }), page.click('#chhanda-details a[href$="#chhanda-' + id + '"]')]);
        assert.equal(await page.$eval('.ln:target', n => n.id), 'chhanda-' + id);
        await waitForPassage();
      }
      if (route.endsWith('/manoladdu')) await page.screenshot({ path: '/tmp/prosody-manoladdu-ending.png', fullPage: false });
    }
    await go('authors/lekhnath_paudyal/kabikabitalap_lalitya_bhag/');
    assert.equal(await page.$('.meta a[href*="chhandas/"]'), null, 'a known ending alone cannot certify the whole poem');
    console.log('PASS: anushtup, nine located passages and an unresolved mixed-form reading');

    for (const [id, name] of [['panchachamara', 'पञ्चचामर'], ['upajati_12', 'द्वादशाक्षरी उपजाति'], ['viyogini', 'वियोगिनी']]) {
      await go('chhandas/' + id + '/');
      assert.ok((await page.$eval('h1', n => n.textContent)).includes(name));
      assert.equal(await page.$('.prosody-write'), null);
    }
    await go('authors/bhimnidhi_tiwari/dagbatti/');
    assert.match(await page.$eval('.meta', n => n.textContent), /छन्द: पञ्चचामर/);
    await page.screenshot({ path: '/tmp/prosody-panchachamara.png', fullPage: false });
    await go('authors/devkota/garib/');
    assert.match(await page.$eval('.meta', n => n.textContent), /छन्द: द्वादशाक्षरी उपजाति/);
    const newMixedCases = [
      ['lekhnath_paudyal/parishranta_chatak', ['shardul-example', 'anushtup-10']],
      ['jagannath_upadhyay_guraganyin/manushyajanma', ['shardul-example', 'shikharini-example', 'drutavilambita-example']],
      ['jagannath_upadhyay_guraganyin/duhkhiko_upakar_gar', ['shardul-example', 'viyogini-ending']],
      ['bhanubhakta_acharya/ramayana', ['shardul-example', 'upajati-example', 'sragdhara-example', 'shikharini-example', 'vasanta-example', 'malini-example']],
      ['lekhnath_paudyal/gangga_gauri', ['malini-example', 'vasanta-example', 'shardul-example', 'vamshastha-example']],
    ];
    for (const [route, ids] of newMixedCases) {
      await go('authors/' + route + '/');
      assert.match(await page.$eval('.meta', n => n.textContent), /छन्द: मिश्रित/);
      assert.equal(await page.$eval('#chhanda-details', n => n.open), false);
      const links = await page.$$eval('#chhanda-details a', nodes => nodes.map(n => ({ href: n.href, hash: new URL(n.href).hash })));
      assert.equal(links.length, ids.length);
      // Capture links before leaving the contents page: long works route to sections.
      for (const id of ids) {
        const link = links.find(n => n.hash === '#chhanda-' + id);
        assert.ok(link, route + ': ' + id);
        await page.goto(link.href, { waitUntil: 'networkidle0' });
        assert.equal(await page.$eval('.ln:target', n => n.id), 'chhanda-' + id);
        await waitForPassage();
      }
      if (route.endsWith('/ramayana')) await page.screenshot({ path: '/tmp/prosody-ramayana-passage.png', fullPage: false });
    }
    console.log('PASS: three archive metre families and seventeen new passage links, including paginated books');

    await go('authors/devkota/pagal/');
    assert.match(await page.$eval('.meta', n => n.textContent), /मुक्तछन्द/);
    await go('chhandas/jhyaure/');
    assert.equal(await page.$('.prosody-write'), null);
    console.log('PASS: reviewed free verse and folk metre remain distinct from writer support');

    await go('chhandas/malini/');
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle0' }), page.click('.prosody-write')]);
    await page.waitForSelector('#chhanda-tool[data-ready=true]');
    assert.equal(await page.$eval('#metre-select', n => n.value), 'malini');
    assert.equal(new URL(page.url()).searchParams.has('metre'), false);
    const draft = 'मेरो सुरक्षित मस्यौदा';
    await page.type('#poem', draft); await pause(250);
    await go('chhandas/shardul/');
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle0' }), page.click('.prosody-write')]);
    await page.waitForSelector('#chhanda-tool[data-ready=true]');
    assert.equal(await page.$eval('#metre-select', n => n.value), 'shardul');
    assert.equal(await page.$eval('#poem', n => n.value), draft);
    await page.click('#undo');
    assert.equal(await page.$eval('#metre-select', n => n.value), 'malini');
    assert.equal(await page.$eval('#poem', n => n.value), draft);
    await page.reload({ waitUntil: 'networkidle0' });
    await page.waitForSelector('#chhanda-tool[data-ready=true]');
    assert.equal(await page.$eval('#metre-select', n => n.value), 'malini');
    assert.equal(await page.$eval('#poem', n => n.value), draft);
    console.log('PASS: writer presets retain existing drafts and can be undone');

    await go('?q=malini');
    await page.waitForSelector('#results a[href*="radhakrishna/"]');
    await go('?q=upajati');
    await page.waitForSelector('#results a[href*="katai_kharani_chhari_bhus_katai/"]');
    await go('?q=anushtup');
    await page.waitForSelector('#results a[href*="manoladdu/"]');
    await go('?q=panchachamara');
    await page.waitForSelector('#results a[href*="dagbatti/"]');
    console.log('PASS: Roman metre names find reviewed works in the main search');
    await page.setViewport({ width: 390, height: 844 });
    await go('chhandas/muktachhanda/');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark')); await pause(350);
    await page.screenshot({ path: '/tmp/prosody-browse-mobile.png', fullPage: false });
    assert.deepEqual(errors, []);
    console.log('PASS: mobile and dark-theme browsing without browser errors');
  } finally { await context.close(); await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
