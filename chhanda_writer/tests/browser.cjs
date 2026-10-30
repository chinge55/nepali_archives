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
    if (request.method() !== 'GET' || request.postData()) draftRequests.push(request.url());
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
    assert.deepEqual(draftRequests, [], 'draft text must not leave the browser');
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
  await test('word suggestions preview and insert a valid next word', async page => {
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
      await page.click(`input[value="${id}"]`);
      await page.evaluate(() => { document.querySelector('#example-panel').open = true; });
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
    await page.click('#final-flexible'); assert.equal(await status(page), 'mismatch');
  });
  await test('pronunciation controls preserve poem text and survive edits and undo', async page => {
    await write(page, 'मन');
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
    await page.click('#download-text');
    assert.equal(await page.evaluate(() => window.lastDownload.text()), poem);
    await page.click('#export-project');
    const project = JSON.parse(await page.evaluate(() => window.lastDownload.text()));
    assert.equal(project.text, poem); assert.equal(project.version, 1);
    await page.click('#clear'); assert.equal(await text(page), '');
    const file = path.join(temporary, 'draft.json'); fs.writeFileSync(file, JSON.stringify(project));
    await (await page.$('#import-project')).uploadFile(file); await pause(250);
    assert.equal(await text(page), poem);
    fs.writeFileSync(file, '{"version":9,"text":"replace"}');
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
  await test('Roman candidates insert at selection and pending text recovers', async page => {
    await page.click('#roman-panel summary');
    await page.waitForFunction(() => document.querySelector('#roman-status').textContent.startsWith('Space'));
    await page.type('#roman', 'kabita'); await page.waitForSelector('#roman-choices button');
    await page.click('#roman-choices button'); assert.equal((await text(page)).trim(), 'कविता');
    await page.type('#roman', 'mero'); await pause(150);
    await page.reload({ waitUntil: 'networkidle0' }); await page.waitForSelector('#chhanda-tool[data-ready=true]');
    assert.equal(await page.$eval('#roman', n => n.value), 'mero');
    assert.equal((await text(page)).trim(), 'कविता');
    await page.$eval('#poem', n => { n.focus(); n.setSelectionRange(0, n.value.trim().length); n.dispatchEvent(new Event('select')); });
    await page.waitForSelector('#roman-choices button'); await page.click('#roman-choices button');
    assert.equal((await text(page)).trim(), 'मेरो');
  });
  await test('storage failure leaves writing, copying and recovery export available', async page => {
    await write(page, 'मेरो कविता'); await page.click('#copy');
    assert.equal(await page.evaluate(() => window.copied), 'मेरो कविता');
    assert.match(await page.$eval('#draft-status', n => n.textContent), /सुरक्षित भएन/);
  }, page => page.evaluateOnNewDocument(() => { Storage.prototype.setItem = () => { throw Error('Storage denied'); }; }));
  await test('shared typing data failure still permits bundled suggestions and direct writing', async page => {
    await write(page, 'नटी '); await page.waitForSelector('#word-choices button');
    await page.click('#roman-panel summary'); await page.waitForSelector('#roman-retry:not([hidden])');
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
    page.on('request', request => /\/chhanda\/engine\.js/.test(request.url()) ? request.abort() : request.continue());
  });
  await test('mobile layout, dark theme and line wrapping preserve pada boundaries', async page => {
    await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true });
    await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'));
    await write(page, 'चिम्ली लोचन दीर्घकाल तपमा खोलेर वासन्तिका ।\nनाच्दी सुन्दर तालले पवनमा देखी फुलेकी लता ॥');
    await page.click('input[value="shardul"]');
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
