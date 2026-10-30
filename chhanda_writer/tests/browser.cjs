/* Run against a built, served site. Set CHHANDA_TEST_URL to test the live route. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const puppeteer = require('puppeteer');
const url = process.env.CHHANDA_TEST_URL || 'http://localhost:8263/chhanda/';
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
let browser, count = 0;
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'chhanda-browser-'));

async function test(name, fn, configure) {
  const context = await browser.createIncognitoBrowserContext();
  const page = await context.newPage(), errors = [], draftRequests = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {
    if (request.method() !== 'GET' || request.postData()) draftRequests.push({ url: request.url(), method: request.method(), body: request.postData() || '' });
  });
  await page.evaluateOnNewDocument(() => {
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async text => { window.copied = text; } } });
    URL.createObjectURL = blob => { window.lastDownload = blob; return 'blob:chhanda-test'; };
    URL.revokeObjectURL = () => {};
    HTMLAnchorElement.prototype.click = function () { window.downloadName = this.download; };
  });
  try {
    if (configure) await configure(page);
    await page.goto(url, { waitUntil: 'networkidle0' });
    if (!name.startsWith('failed analysis')) await page.waitForSelector('#chhanda-tool[data-ready=true]');
    await fn(page);
    assert.deepEqual(errors, [], 'uncaught browser errors');
    for (const request of draftRequests) {
      // Identify the host's own metrics separately from editor/API requests.
      assert.equal(new URL(request.url).pathname, '/cdn-cgi/rum', 'unexpected outbound request');
      assert.equal(new URL(request.url).origin, new URL(url).origin);
      assert.equal(request.method, 'POST');
      // The browser protocol omits some unload-beacon bodies during reload.
      if (!request.body) continue;
      const metrics = JSON.parse(request.body);
      assert.ok(!['text', 'poem', 'draft', 'pending', 'input'].some(key => key in metrics), 'editor data in host beacon');
      if (metrics.location) assert.equal(metrics.location, url, 'draft must not enter the page URL');
      assert.doesNotMatch(request.body, /[\u0900-\u097f]|%e0%a[45]|\\u09[0-7][0-9a-f]/i, 'draft text must not leave the browser');
    }
    console.log(`PASS ${++count}: ${name}`);
  } finally { await context.close(); }
}
async function write(page, text) {
  await page.focus('#poem');
  await page.keyboard.down('Control'); await page.keyboard.press('KeyA'); await page.keyboard.up('Control');
  await page.keyboard.sendCharacter(text); await pause(250);
}
const text = page => page.$eval('#poem', node => node.value);
const status = page => page.$eval('#analysis-status', node => node.dataset.status);

(async () => {
  browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
  await test('the initial surface is one writer with a toggle and metre dropdown', async page => {
    assert.equal(await page.$$eval('textarea', nodes => nodes.length), 1);
    assert.equal(await page.$$eval('#metre-select option', nodes => nodes.length), 3);
    assert.equal(await page.$$eval('#roman', nodes => nodes.length), 0);
    assert.equal(await page.$eval('#example-dialog', node => node.open), false);
    for (const id of ['analysis-panel', 'word-panel', 'help-panel']) assert.equal(await page.$eval('#' + id, node => node.open), false);
    await page.select('#metre-select', 'shardul');
    assert.equal(await page.$eval('#example-dialog', node => node.open), false);
    await page.screenshot({ path: path.join(temporary, 'writer-empty.png'), fullPage: true });
  });
  await test('examples open only when requested and closing them preserves writing', async page => {
    await write(page, 'आफ्नो कविता');
    await page.select('#metre-select', 'vasanta');
    assert.equal(await text(page), 'आफ्नो कविता');
    assert.equal(await page.$eval('#example-dialog', n => n.open), false);
    await page.click('#example-open'); assert.equal(await page.$eval('#example-dialog', n => n.open), true);
    await page.click('#example-close'); assert.equal(await text(page), 'आफ्नो कविता');
  });
  await test('soft problem underlines preserve writing and clear after correction or during composition', async page => {
    const good = 'नटी मेनका छम्छमाउन् अगाडि';
    const bad = good.replace('नटी', 'नाटी');
    await write(page, bad);
    await page.waitForSelector('.ch-problem-underline');
    const before = await page.$eval('#poem', n => [n.selectionStart, n.selectionEnd, n.value]);
    assert.equal(await page.$eval('.ch-problem-underline', n => n.dataset.start), '0');
    assert.equal(await page.$eval('.ch-problem-underline', n => n.dataset.end), '2');
    assert.equal(await page.$eval('#poem-underlines', n => getComputedStyle(n).pointerEvents), 'none');
    assert.equal(await page.$eval('#analysis-panel', n => n.open), false);
    await pause(150);
    assert.deepEqual(await page.$eval('#poem', n => [n.selectionStart, n.selectionEnd, n.value]), before);
    assert.equal(await page.evaluate(() => document.activeElement.id), 'poem');
    await page.screenshot({ path: path.join(temporary, 'soft-underlines.png'), fullPage: true });
    await page.$eval('#poem', n => n.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true })));
    assert.equal(await page.$$('.ch-problem-underline').then(nodes => nodes.length), 0);
    await page.$eval('#poem', n => n.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true })));
    await page.waitForSelector('.ch-problem-underline');
    await write(page, good); assert.equal(await page.$$('.ch-problem-underline').then(nodes => nodes.length), 0);
    await write(page, 'नटी'); assert.equal(await page.$$('.ch-problem-underline').then(nodes => nodes.length), 0);
    await page.keyboard.press('Enter'); await page.waitForSelector('.ch-problem-underline');
    assert.equal(await text(page), 'नटी\n');
  });
  await test('underlines follow wrapping and textarea scrolling on a narrow screen', async page => {
    await page.setViewport({ width: 390, height: 844 });
    const bad = 'नाटी मेनका छम्छमाउन् अगाडि मनको कविता सुन्दर हिमालको सम्झनामा';
    const poem = Array(8).fill(bad).join('\n');
    await write(page, poem);
    await page.$eval('#poem', n => {
      n.style.height = n.style.minHeight = n.style.maxHeight = '190px';
      n.scrollTop = 0; n.dispatchEvent(new Event('scroll'));
    });
    await page.waitForSelector('.ch-problem-underline[data-start="0"]'); await pause(100);
    assert.ok(await page.$eval('#poem-measure', n => n.scrollHeight > 8 * parseFloat(getComputedStyle(n).lineHeight)), 'long lines must actually wrap');
    const firstTop = await page.$eval('.ch-problem-underline[data-start="0"]', n => parseFloat(n.style.top));
    await page.$eval('#poem', n => { n.scrollTop = 20; n.dispatchEvent(new Event('scroll')); });
    await pause(100);
    const movedTop = await page.$eval('.ch-problem-underline[data-start="0"]', n => parseFloat(n.style.top));
    assert.ok(Math.abs(firstTop - movedTop - 20) < 1, 'underlines must scroll with the text');
    assert.equal(await text(page), poem);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'));
    await pause(300);
    await page.screenshot({ path: path.join(temporary, 'soft-underlines-mobile.png'), fullPage: true });
  });
  await test('word suggestions preview and insert a valid next word', async page => {
    await page.click('#word-panel > summary');
    await write(page, 'नटी ');
    assert.equal(await status(page), 'partial');
    await page.type('#word-prefix', 'मे');
    await page.waitForFunction(() => [...document.querySelectorAll('#word-choices button')].some(b => b.textContent === 'मेनका'));
    await page.evaluate(() => [...document.querySelectorAll('#word-choices button')].find(b => b.textContent === 'मेनका').click());
    assert.equal(await text(page), 'नटी ');
    assert.equal(await page.$eval('#preview-line', node => node.textContent), 'नटी मेनका');
    await page.click('#insert-word'); assert.equal(await text(page), 'नटी मेनका');
    assert.equal(await status(page), 'partial');
  });
  await test('all three source examples and a full stanza are analysed', async page => {
    for (const id of ['bhujanga', 'vasanta', 'shardul']) {
      await page.select('#metre-select', id);
      await page.click('#example-open');
      await page.click('#use-example'); await pause(150);
      assert.equal(await status(page), 'match');
      assert.equal(await page.$$eval('.ch-pada[data-status=match]', nodes => nodes.length), id === 'bhujanga' ? 4 : 2);
    }
    await page.screenshot({ path: path.join(temporary, 'desktop.png'), fullPage: true });
  });
  await test('final-syllable licence is visible and optional', async page => {
    await write(page, 'नटी मेनका छम्छमाउन् अगाडि');
    assert.equal(await status(page), 'match');
    assert.match(await page.$eval('#analysis-status', n => n.textContent), /पदान्त/);
    await page.click('#analysis-panel > summary');
    await page.click('#final-flexible'); assert.equal(await status(page), 'mismatch');
  });
  await test('pronunciation controls preserve poem text and survive edits and undo', async page => {
    await write(page, 'मन');
    await page.click('#analysis-panel > summary');
    await page.evaluate(() => { document.querySelector('#reading-panel').open = true; });
    await page.select('#reading-choices select', 'drop');
    assert.equal(await text(page), 'मन');
    assert.match(await page.$eval('#counts', n => n.textContent), /^१ \/ १२/);
    await page.focus('#poem'); await page.keyboard.press('End'); await page.keyboard.sendCharacter(' वन'); await pause(250);
    assert.equal(await page.$eval('#reading-choices select', n => n.value), 'drop');
    await page.click('#undo'); assert.equal(await text(page), 'मन');
    await page.click('#redo'); assert.equal(await text(page), 'मन वन');
    await write(page, 'मनको वन');
    assert.equal(await page.$eval('#reading-choices select', n => n.value), 'keep');
  });
  await test('copy, recovery, TXT and project export preserve exact text', async page => {
    const poem = 'नटी मेनका\n\nकविता <img src=x onerror="window.injected=1">';
    await write(page, poem); await page.click('#copy');
    assert.equal(await page.evaluate(() => window.copied), poem);
    assert.equal(await page.evaluate(() => window.injected), undefined);
    await page.reload({ waitUntil: 'networkidle0' }); await page.waitForSelector('#chhanda-tool[data-ready=true]');
    assert.equal(await text(page), poem);
    await page.click('.ch-file-menu > summary'); await page.click('#download-text');
    assert.equal(await page.evaluate(() => window.lastDownload.text()), poem);
    await page.click('#export-project');
    const project = JSON.parse(await page.evaluate(() => window.lastDownload.text()));
    assert.equal(project.text, poem); assert.equal(project.version, 2);
    await page.click('#clear'); assert.equal(await text(page), '');
    const file = path.join(temporary, 'draft.json'); fs.writeFileSync(file, JSON.stringify(project));
    await page.click('.ch-file-menu > summary');
    await (await page.$('#import-project')).uploadFile(file); await pause(250);
    assert.equal(await text(page), poem);
    fs.writeFileSync(file, '{"version":9,"text":"replace"}');
    await page.click('.ch-file-menu > summary');
    await (await page.$('#import-project')).uploadFile(file); await pause(250);
    assert.equal(await text(page), poem);
  });
  await test('keyboard composition preserves input and defers analysis', async page => {
    await write(page, 'नटी');
    await page.$eval('#poem', node => {
      node.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true }));
      node.value = 'नटी मेनका'; node.setSelectionRange(node.value.length, node.value.length);
      node.dispatchEvent(new InputEvent('input', { bubbles: true, isComposing: true }));
    });
    await pause(100); assert.match(await page.$eval('#counts', n => n.textContent), /^२ \/ १२/);
    await page.$eval('#poem', node => node.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true })));
    await pause(250); assert.match(await page.$eval('#counts', n => n.textContent), /^५ \/ १२/);
    await page.click('#undo'); assert.equal(await text(page), 'नटी');
  });
  await test('clipboard fallback keeps the text captured when copy was pressed', async page => {
    await write(page, 'नटी');
    await page.evaluate(() => {
      navigator.clipboard.writeText = () => new Promise((_, reject) => { window.rejectCopy = reject; });
      document.execCommand = () => { window.copied = document.activeElement.value; return true; };
    });
    await page.click('#copy'); await write(page, 'मेनका');
    await page.evaluate(() => window.rejectCopy(Error('Denied')));
    await page.waitForFunction(() => window.copied !== undefined);
    assert.equal(await page.evaluate(() => window.copied), 'नटी');
    assert.equal(await text(page), 'मेनका');
  });
  await test('Roman writing stays in the main editor and pending words recover', async page => {
    await page.click('#roman-mode');
    await page.waitForSelector('#chhanda-tool[data-typing-ready=true]');
    await page.type('#poem', 'kabita'); await page.waitForSelector('#roman-choices button');
    await page.click('#roman-choices button'); assert.equal((await text(page)).trim(), 'कविता');
    await page.type('#poem', ' mero'); await pause(150);
    await page.reload({ waitUntil: 'networkidle0' }); await page.waitForSelector('#chhanda-tool[data-ready=true]');
    assert.equal(await text(page), 'कविता mero');
    assert.equal(await page.$eval('#roman-mode', n => n.checked), true);
    await page.waitForSelector('#chhanda-tool[data-typing-ready=true]');
    await page.focus('#poem'); await page.keyboard.press('End'); await page.keyboard.type(' '); await pause(200);
    assert.equal(await text(page), 'कविता मेरो ');
    await write(page, 'mero naam ho\n'); assert.equal(await text(page), 'मेरो नाम हो\n');
    await page.click('#roman-mode'); await write(page, 'mero'); assert.equal(await text(page), 'mero');
  });
  await test('inline Roman conversion replaces a selection and defers keyboard composition', async page => {
    await write(page, 'मेरो नाम हो');
    await page.click('#roman-mode'); await page.waitForSelector('#chhanda-tool[data-typing-ready=true]');
    await page.$eval('#poem', n => { n.focus(); n.setSelectionRange(5, 8); n.dispatchEvent(new Event('select')); });
    await page.keyboard.type('kabita '); await pause(200);
    assert.equal(await text(page), 'मेरो कविता  हो');
    await page.$eval('#poem', n => {
      n.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true }));
      n.value = 'mero '; n.setSelectionRange(5, 5);
      n.dispatchEvent(new InputEvent('input', { bubbles: true, isComposing: true }));
    });
    await pause(100); assert.equal(await text(page), 'mero ');
    await page.$eval('#poem', n => n.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true })));
    await pause(200); assert.equal(await text(page), 'मेरो ');
  });
  let heldRules;
  await test('words typed while Roman rules load convert without losing boundaries', async page => {
    await page.click('#roman-mode'); await page.type('#poem', 'mero naam ');
    assert.equal(await text(page), 'mero naam ');
    await heldRules.continue();
    await page.waitForFunction(() => document.querySelector('#poem').value === 'मेरो नाम ');
  }, async page => {
    await page.setRequestInterception(true);
    page.on('request', request => request.url().includes('/type/rules.json') ? heldRules = request : request.continue());
  });
  await test('the first release draft migrates its pending word into the main writer', async page => {
    assert.equal(await text(page), 'कविता mero');
    assert.equal(await page.$eval('#metre-select', n => n.value), 'vasanta');
    assert.equal(await page.$eval('#roman-mode', n => n.checked), true);
    await page.waitForSelector('#chhanda-tool[data-typing-ready=true]');
    await page.focus('#poem'); await page.keyboard.press('End'); await page.keyboard.type(' '); await pause(200);
    assert.equal(await text(page), 'कविता मेरो ');
  }, page => page.evaluateOnNewDocument(() => {
    localStorage.setItem('nepaliarchives:chhanda:draft:v1', JSON.stringify({ version: 1, text: 'कविता ', pending: 'mero', metre: 'vasanta', overrides: {}, finalFlexible: false }));
  }));
  await test('storage failure leaves writing, copying and recovery export available', async page => {
    await write(page, 'मेरो कविता'); await page.click('#copy');
    assert.equal(await page.evaluate(() => window.copied), 'मेरो कविता');
    assert.match(await page.$eval('#draft-status', n => n.textContent), /सुरक्षित भएन/);
  }, page => page.evaluateOnNewDocument(() => { Storage.prototype.setItem = () => { throw Error('Storage denied'); }; }));
  await test('shared typing data failure still permits bundled suggestions and direct writing', async page => {
    await write(page, 'नटी '); await page.click('#word-panel > summary'); await page.waitForSelector('#word-choices button');
    await page.click('#roman-mode'); await page.waitForSelector('#roman-retry:not([hidden])');
    assert.equal(await text(page), 'नटी ');
  }, async page => {
    await page.setRequestInterception(true);
    page.on('request', request => request.url().includes('/type/') ? request.abort() : request.continue());
  });
  await test('failed analysis dependencies retry without losing early input', async page => {
    await page.waitForSelector('#boot-retry:not([hidden])');
    await page.type('#poem', 'कविता');
    page.removeAllListeners('request'); await page.setRequestInterception(false);
    await page.click('#boot-retry'); await page.waitForSelector('#chhanda-tool[data-ready=true]');
    assert.equal(await text(page), 'कविता');
  }, async page => {
    await page.setRequestInterception(true);
    page.on('request', request => /\/chhanda\/(?:engine|inline)\.js/.test(request.url()) ? request.abort() : request.continue());
  });
  await test('mobile layout, dark theme and line wrapping preserve pada boundaries', async page => {
    await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true });
    await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'));
    await write(page, 'चिम्ली लोचन दीर्घकाल तपमा खोलेर वासन्तिका ।\nनाच्दी सुन्दर तालले पवनमा देखी फुलेकी लता ॥');
    await page.select('#metre-select', 'shardul');
    assert.equal(await page.$$eval('.ch-pada', n => n.length), 2);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({ path: path.join(temporary, 'mobile-dark.png'), fullPage: true });
    await page.setViewport({ width: 390, height: 400, isMobile: true, hasTouch: true });
    await page.focus('#poem');
    await page.waitForFunction(() => document.body.classList.contains('ch-keyboard'));
    assert.ok(await page.$eval('#poem', n => n.getBoundingClientRect().height < 180));
    assert.match(await page.$eval('#editor-live-status', n => n.textContent), /मिल्यो/);
  });
  console.log(`${count} browser scenarios passed. Screenshots: ${temporary}`);
})().catch(error => { console.error(error); process.exitCode = 1; }).finally(async () => {
  if (browser) await browser.close();
});
