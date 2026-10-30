/* Verify the current calendar and the two stale-cache fallback paths. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const puppeteer = require('puppeteer');
const url = process.env.PATRO_TEST_URL || 'http://localhost:8262/patro/';
const root = path.resolve(__dirname, '../../..');
const content = path.join(root, 'horoscope/content');
const days = Object.assign({}, ...fs.readdirSync(content).filter(name => /^panchanga-.*\.json$/.test(name))
  .map(name => JSON.parse(fs.readFileSync(path.join(content, name))).days));
const today = new Date(Date.now() + 20700000).toISOString().slice(0, 10);
const nextDay = new Date(Date.parse(today) + 86400000).toISOString().slice(0, 10);
const expired = new Date(Date.parse(Object.keys(days).sort().at(-1)) + 86400000).toISOString().slice(0, 10);

(async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
  async function test(name, date, fn) {
    const context = await browser.createIncognitoBrowserContext();
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    try {
      if (date) await page.evaluateOnNewDocument(iso => { Date.now = () => Date.parse(iso + 'T12:00:00+05:45'); }, date);
      await page.goto(url, { waitUntil: 'networkidle0' });
      await fn(page);
      assert.deepEqual(errors, []);
      console.log('PASS:', name);
    } finally { await context.close(); }
  }
  try {
    assert.ok(days[today], 'the committed calendar must cover today');
    await test('today displays the correct Nepali date and calculated panchanga', null, async page => {
      assert.ok((await page.$eval('.pt-date', n => n.textContent)).includes(today));
      assert.ok((await page.$eval('.pt-bs', n => n.textContent)).includes(days[today].bs_str));
      const cells = await page.$$eval('.pt-panch b', nodes => nodes.map(n => n.textContent));
      assert.deepEqual(cells, ['tithi', 'nakshatra', 'yoga', 'karana', 'moon_rashi'].map(key => days[today][key].name));
      assert.equal(await page.$$eval('.zt', nodes => nodes.length), 12);
      if (await page.$('#patro-stale')) assert.equal(await page.$eval('#patro-stale', n => getComputedStyle(n).display), 'none');
      await page.click('.zt');
      assert.equal(await page.$eval('.zt', n => n.getAttribute('aria-pressed')), 'true');
      if (process.env.PATRO_SCREENSHOT) await page.screenshot({ path: process.env.PATRO_SCREENSHOT, fullPage: true });
    });
    assert.ok(days[nextDay], 'tomorrow must be available for the stale-cache redirect');
    await test('a cached page redirects to the current dated calendar', nextDay, async page => {
      await page.waitForFunction(iso => location.pathname.endsWith('/' + iso + '/'), {}, nextDay);
      assert.ok((await page.$eval('.pt-date', n => n.textContent)).includes(nextDay));
    });
    await test('exhausted calendar coverage displays a clear stale notice', expired, async page => {
      assert.equal(await page.$eval('#patro-stale', n => getComputedStyle(n).display), 'block');
      assert.match(await page.$eval('#patro-stale', n => n.textContent), /पुरानो/);
      assert.ok(!(await page.$eval('.pt-date', n => n.textContent)).includes(expired));
    });
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
