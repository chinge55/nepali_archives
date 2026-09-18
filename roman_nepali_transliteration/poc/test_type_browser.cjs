/* Browser regressions for the built /type/ page.
 * Build the site and serve it, then run with puppeteer available on NODE_PATH:
 * TYPE_TEST_URL=http://localhost:8261/type/ node roman_nepali_transliteration/poc/test_type_browser.cjs
 * Clipboard assertions capture the API argument, not the operating-system clipboard.
 */
const assert = require('node:assert/strict');
const puppeteer = require('puppeteer');
const url = process.env.TYPE_TEST_URL || 'http://localhost:8261/type/';
let browser, count = 0;
const pause = ms => new Promise(r => setTimeout(r, ms));
async function test(name, fn, configure) {
  if (process.env.TYPE_TEST_FILTER && !new RegExp(process.env.TYPE_TEST_FILTER).test(name)) return;
  const context = await browser.createIncognitoBrowserContext();
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.evaluateOnNewDocument(() => {
    window.copied = null;
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: {
      writeText: async text => { window.copied = text; }
    }});
  });
  try {
    if (configure) await configure(page);
    await page.goto(url, {waitUntil: configure ? 'domcontentloaded' : 'networkidle0'});
    await fn(page);
    assert.deepEqual(errors, [], 'uncaught browser errors');
    console.log(`PASS ${++count}: ${name}`);
  } finally { await context.close(); }
}
const output = p => p.$eval('#out', el => el.value);
const input = (p, text) => p.type('#inp', text);
const copy = async p => { await p.click('#copy'); await p.waitForFunction(() => window.copied !== null); return p.evaluate(() => window.copied); };
(async () => {
  browser = await puppeteer.launch({headless:'new',args:['--no-sandbox']});
  await test('ordinary sentence', async p => {
    await input(p, 'mero naam ho '); assert.equal(await output(p), 'मेरो नाम हो ');
  });
  for (const [raw, expected] of [['2081','२०८१ '],['.','। '],['naam.','नाम। ']]) {
    await test(`candidate click preserves ${raw}`, async p => {
      await input(p,raw); await p.click('.tcand.first'); assert.equal(await output(p),expected);
    });
  }
  await test('copy commits pending punctuation and copies exact visible text', async p => {
    await input(p,'mero naam.'); const text = await copy(p);
    assert.equal(text,'मेरो नाम। '); assert.equal(text,await output(p));
  });
  await test('copy commits pending digits', async p => {
    await input(p,'2081'); assert.equal(await copy(p),'२०८१ ');
  });
  await test('copy fallback includes pending text', async p => {
    await p.evaluate(() => {
      navigator.clipboard.writeText = async () => { throw Error('denied'); };
      document.execCommand = command => {
        if (command !== 'copy') return false;
        const el = document.activeElement;
        window.copied = el.value.slice(el.selectionStart,el.selectionEnd); return true;
      };
    });
    await input(p,'mero naam'); assert.equal(await copy(p),'मेरो नाम ');
  });
  await test('copy replaces selected text', async p => {
    await input(p,'mero naam ');
    await p.$eval('#out', el => { el.focus(); el.setSelectionRange(5,8); });
    await input(p,'ghar'); assert.equal(await copy(p),'मेरो घर ');
  });
  await test('pasted HTML stays literal and inert', async p => {
    const payload = "<img/src='missing'/onerror='window.injected=1'>";
    await p.focus('#inp'); await p.keyboard.sendCharacter(payload); await pause(100);
    assert.equal(await p.$eval('#cands', el => el.querySelectorAll('img,svg,b').length),0);
    assert.equal(await p.evaluate(() => window.injected),undefined);
    await p.click('.tcand.first'); assert.equal((await output(p)).trim(),payload);
  });
  await test('failed rules show retry and preserve early input', async p => {
    await p.waitForSelector('#retry:not([hidden])');
    await input(p,'mero naam ');
    assert.equal(await p.$eval('#inp', el => el.value),'mero naam ');
    assert.equal(await output(p),'');
    p.removeAllListeners('request'); await p.setRequestInterception(false); await p.click('#retry');
    await p.waitForFunction(() => document.querySelector('#out').value.includes(' '));
    assert.equal((await output(p)).trim().split(/\s+/).length,2);
  }, async p => {
    await p.setRequestInterception(true);
    p.on('request',r => r.url().includes('/rules.json') ? r.abort() : r.continue());
  });
  let held;
  await test('typing during initial loading preserves word boundaries', async p => {
    await input(p,'mero naam '); await held.continue();
    await p.waitForFunction(() => document.querySelector('#out').value.includes(' '));
    assert.equal((await output(p)).trim().split(/\s+/).length,2);
  }, async p => {
    await p.setRequestInterception(true);
    p.on('request',r => r.url().includes('/rules.json') ? held=r : r.continue());
  });
  await test('late English dictionary refreshes displayed and committed candidate', async p => {
    await p.waitForFunction(() => document.querySelector('#status').textContent === '');
    await input(p,'hello'); await held.continue();
    await p.waitForFunction(() => document.querySelector('.tcand.first')?.textContent.includes('hello'));
    await p.keyboard.sendCharacter(' '); assert.equal(await output(p),'hello ');
  }, async p => {
    await p.setRequestInterception(true);
    p.on('request',r => r.url().includes('/english.json') ? held=r : r.continue());
  });
  await test('refresh restores output, pending input, mode, and selection', async p => {
    await input(p, 'mero naam'); await p.click('#engmode');
    await p.$eval('#out', el => el.setSelectionRange(0,4));
    await pause(350); await p.reload({waitUntil:'networkidle0'});
    assert.equal(await output(p),'मेरो ');
    assert.equal(await p.$eval('#inp',el => el.value),'naam');
    assert.equal(await p.$eval('#engmode',el => el.checked),false);
    assert.deepEqual(await p.$eval('#out',el => [el.selectionStart,el.selectionEnd]),[0,4]);
  });
  await test('conversion can be undone and redone', async p => {
    await input(p,'mero '); await p.click('#undo');
    assert.equal(await output(p),''); assert.equal(await p.$eval('#inp',el=>el.value),'mero');
    await p.click('#redo'); assert.equal(await output(p),'मेरो ');
    await p.focus('#out'); await p.keyboard.down('Control'); await p.keyboard.press('z'); await p.keyboard.up('Control');
    assert.equal(await output(p),'');
    await p.keyboard.down('Control'); await p.keyboard.down('Shift'); await p.keyboard.press('z');
    await p.keyboard.up('Shift'); await p.keyboard.up('Control');
    assert.equal(await output(p),'मेरो ');
  });
  await test('clear removes saved draft and undo restores committed and pending text', async p => {
    await input(p,'mero naam'); await pause(300); await p.click('#clear');
    assert.equal(await output(p),'');
    assert.equal(await p.evaluate(() => localStorage.getItem('nepaliarchives:type:draft:v1')),null);
    await p.click('#undo'); assert.equal(await output(p),'मेरो ');
    assert.equal(await p.$eval('#inp',el=>el.value),'naam');
    await p.reload({waitUntil:'networkidle0'}); assert.equal(await output(p),'मेरो ');
  });
  await test('clearing pending-only text is undoable', async p => {
    await input(p,'mero'); await p.click('#clear'); await p.click('#undo');
    assert.equal(await p.$eval('#inp',el=>el.value),'mero');
  });
  await test('deleting all output does not lock direct editing', async p => {
    await input(p,'mero '); await p.focus('#out');
    await p.keyboard.down('Control'); await p.keyboard.press('a'); await p.keyboard.up('Control');
    await p.keyboard.press('Backspace');
    assert.equal(await p.$eval('#out',el=>el.readOnly),false);
    await p.keyboard.sendCharacter('नाम'); assert.equal(await output(p),'नाम');
    await p.click('#undo'); assert.equal(await output(p),'');
    await p.click('#undo'); assert.equal(await output(p),'मेरो ');
  });
  await test('unavailable storage does not prevent typing or copying', async p => {
    await input(p,'mero naam'); await pause(350);
    assert.match(await p.$eval('#draftstatus',el=>el.textContent),/unavailable/);
    assert.equal(await copy(p),'मेरो नाम ');
  }, async p => {
    await p.evaluateOnNewDocument(() => {
      Storage.prototype.setItem = () => { throw Error('storage unavailable'); };
    });
  });
  await test('malformed saved draft does not crash the tool', async p => {
    await input(p,'mero '); assert.equal(await output(p),'मेरो ');
  }, async p => {
    await p.evaluateOnNewDocument(() => localStorage.setItem('nepaliarchives:type:draft:v1','{bad'));
  });
  await test('English case and structured tokens survive normal typing', async p => {
    await input(p,'School SMS OK covid19 gopal@home mero,naam ');
    assert.equal(await output(p),'School SMS OK covid19 gopal@home mero,naam ');
  });
  await test('dates and decimals preserve their separators', async p => {
    await input(p,'2081-01-02 3.14 '); assert.equal(await output(p),'२०८१-०१-०२ ३.१४ ');
  });
  await test('plain digits type normally and modified shortcuts select candidates', async p => {
    await input(p,'naam');
    const second = await p.$eval('.tcand:nth-child(2)',el=>el.lastChild.textContent);
    await p.keyboard.down('Alt'); await p.keyboard.press('2'); await p.keyboard.up('Alt');
    assert.equal((await output(p)).trim(),second);
  });
  await test('Enter starts a line and Shift+Enter a paragraph', async p => {
    await input(p,'mero'); await p.keyboard.press('Enter'); await input(p,'naam');
    await p.keyboard.down('Shift'); await p.keyboard.press('Enter'); await p.keyboard.up('Shift');
    await input(p,'ho '); assert.equal(await output(p),'मेरो\nनाम\n\nहो ');
  });
  await test('paragraph button finalizes pending input', async p => {
    await input(p,'mero'); await p.click('#paragraph'); await input(p,'naam ');
    assert.equal(await output(p),'मेरो\n\nनाम ');
  });
  await test('pasted paragraph boundaries survive conversion and copy', async p => {
    await p.focus('#inp'); await p.keyboard.sendCharacter('mero naam\n\ntimro naam');
    assert.equal(await copy(p),'मेरो नाम\n\nतिम्रो नाम ');
  });
  await test('composition is not committed until composition ends', async p => {
    await p.$eval('#inp',el => {
      el.dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true}));
      el.value='mero ';
      el.dispatchEvent(new InputEvent('input',{bubbles:true,isComposing:true}));
    });
    assert.equal(await output(p),'');
    await p.$eval('#inp',el => el.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true})));
    assert.equal(await output(p),'मेरो ');
  });
  await test('backspace reopens word at the output cursor', async p => {
    await input(p,'mero naam ');
    await p.$eval('#out',el=>el.setSelectionRange(5,5)); await p.focus('#inp');
    await p.keyboard.press('Backspace');
    assert.equal(await p.$eval('#inp',el=>el.value),'mero');
    assert.deepEqual(await p.$eval('#out',el=>[el.selectionStart,el.selectionEnd]),[0,4]);
    await p.keyboard.down('Control'); await p.keyboard.press('a'); await p.keyboard.up('Control');
    await input(p,'timro '); assert.equal(await output(p),'तिम्रो नाम ');
  });
  await test('suggestions are reachable and selectable using only the keyboard', async p => {
    await input(p,'naam'); await p.keyboard.press('Tab');
    assert.equal(await p.evaluate(() => document.activeElement.classList.contains('tcand')),true);
    await p.keyboard.press('ArrowRight');
    const choice = await p.evaluate(() => document.activeElement.dataset.value);
    await p.keyboard.press('Enter'); assert.equal((await output(p)).trim(),choice);
    assert.equal(await p.evaluate(() => document.activeElement.id),'inp');
  });
  await test('mobile input stays visible and stable as suggestions change', async p => {
    await p.setViewport({width:375,height:667});
    const before = await p.$eval('#inp',el=>el.getBoundingClientRect().top);
    assert.ok(before < 400, `input begins at ${before}`);
    await input(p,'naam');
    assert.equal(await p.$eval('#inp',el=>el.getBoundingClientRect().top),before);
    assert.ok(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await p.setViewport({width:320,height:568});
    assert.ok(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  });
  await test('simulated keyboard mode retains essential controls', async p => {
    await p.setViewport({width:375,height:360});
    await p.evaluate(() => document.body.classList.add('kbd'));
    for (const id of ['inp','out','copy','engmode','undo','redo','paragraph','clear']) {
      assert.ok(await p.$eval('#'+id,el=>el.getBoundingClientRect().height > 0),id+' is visible');
    }
    assert.ok(await p.$eval('#copy',el=>el.getBoundingClientRect().bottom < innerHeight));
    assert.ok(await p.$eval('#engmode',el=>el.getBoundingClientRect().bottom < innerHeight));
    assert.ok(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  });
  await test('clipboard fallback copies the original snapshot after a delayed failure', async p => {
    await p.evaluate(() => {
      navigator.clipboard.writeText = () => new Promise((resolve,reject) => { window.rejectCopy = reject; });
      document.execCommand = () => { window.copied = document.activeElement.value; return true; };
    });
    await input(p,'mero naam'); await p.click('#copy');
    await input(p,'ho '); await p.evaluate(() => window.rejectCopy(Error('denied')));
    await p.waitForFunction(() => window.copied !== null);
    assert.equal(await p.evaluate(() => window.copied),'मेरो नाम ');
    assert.equal(await output(p),'मेरो नाम हो ');
  });
  await test('copy reports failure when both clipboard paths fail', async p => {
    await p.evaluate(() => {
      navigator.clipboard.writeText = async () => { throw Error('denied'); };
      document.execCommand = () => false;
    });
    await input(p,'mero'); await p.click('#copy');
    assert.match(await p.$eval('#toast',el=>el.textContent),/मिलेन/);
    assert.equal(await output(p),'मेरो ');
  });
  await test('clear followed by refresh does not resurrect the draft', async p => {
    await input(p,'mero naam'); await p.click('#clear');
    await p.reload({waitUntil:'networkidle0'});
    assert.equal(await output(p),''); assert.equal(await p.$eval('#inp',el=>el.value),'');
  });
  await test('undoing a replacement restores its output selection and pending word', async p => {
    await input(p,'mero naam ');
    await p.$eval('#out',el=>el.setSelectionRange(5,8)); await input(p,'ghar ');
    assert.equal(await output(p),'मेरो घर '); await p.click('#undo');
    assert.equal(await output(p),'मेरो नाम ');
    assert.equal(await p.$eval('#inp',el=>el.value),'ghar');
    assert.deepEqual(await p.$eval('#out',el=>[el.selectionStart,el.selectionEnd]),[5,8]);
  });
  await test('dictionary failure leaves basic typing and a visible explanation', async p => {
    await p.waitForFunction(() => document.querySelector('#status').textContent.includes('unavailable'));
    await input(p,'mero '); assert.ok((await output(p)).trim().length > 0);
    assert.match(await p.$eval('#status',el=>el.textContent),/basic typing/);
  }, async p => {
    await p.setRequestInterception(true);
    p.on('request',r => /lexicon-(core|full)\.json/.test(r.url()) ? r.abort() : r.continue());
  });
  await test('failed engine module can be retried without losing typed text', async p => {
    await p.waitForSelector('#retry:not([hidden])'); await input(p,'mero naam ');
    p.removeAllListeners('request'); await p.setRequestInterception(false); await p.click('#retry');
    await p.waitForFunction(() => document.querySelector('#out').value.trim().split(/\s+/).length === 2);
    assert.equal(await p.$eval('#inp',el=>el.value),'');
  }, async p => {
    await p.setRequestInterception(true);
    p.on('request',r => r.url().includes('/engine.js') ? r.abort() : r.continue());
  });
  await test('reopening manually edited text preserves its punctuation', async p => {
    await input(p,'mero '); await p.focus('#out');
    await p.keyboard.down('Control'); await p.keyboard.press('a'); await p.keyboard.up('Control');
    await p.keyboard.sendCharacter('नाम, '); await p.focus('#inp');
    await p.keyboard.press('Backspace');
    assert.match(await p.$eval('#inp',el=>el.value),/,$/);
    await p.keyboard.press('Space'); assert.equal(await output(p),'नाम, ');
  });
  console.log(`All ${count} browser regressions passed.`);
})().catch(e => { console.error(e); process.exitCode=1; }).finally(async () => { await browser?.close(); });
