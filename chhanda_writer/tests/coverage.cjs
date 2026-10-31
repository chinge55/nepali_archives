/* Every archive category opens an appropriate writing mode and retains the draft. */
const assert = require('node:assert/strict');
const puppeteer = require('puppeteer');
const url = process.env.CHHANDA_TEST_URL || 'http://localhost:8263/kavita-lekhan/';
const base = new URL('../',url).href;
const pause = ms => new Promise(resolve => setTimeout(resolve,ms));

(async () => {
  const browser = await puppeteer.launch({headless:'new',args:['--no-sandbox']});
  try {
    const page = await browser.newPage(), errors = [];
    page.on('pageerror',error => errors.push(error.message));
    async function ready() { await page.waitForSelector('#chhanda-tool[data-ready=true]'); }
    async function write(text) {
      await page.focus('#poem');
      await page.keyboard.down('Control'); await page.keyboard.press('KeyA'); await page.keyboard.up('Control');
      await page.keyboard.sendCharacter(text); await pause(150);
    }
    await page.setViewport({width:1280,height:1000});
    await page.goto(url,{waitUntil:'networkidle2'}); await ready();
    const entries = await page.evaluate(async () => (await (await fetch('writer-data.json')).json()).metres);
    assert.equal(entries.length,32);
    assert.equal(await page.$$eval('#metre-select option',nodes => nodes.length),32);
    const draft = 'मेरो आफ्नै मस्यौदा';
    await write(draft);
    for (const entry of entries) {
      await page.goto(base+'chhandas/'+entry.id+'/',{waitUntil:'networkidle2'});
      assert.equal(await page.$eval('.metre-guide',n=>n.open),false);
      await page.click('.metre-guide > summary');
      assert.equal(new URL(await page.$eval('.prosody-write',n=>n.href)).searchParams.get('metre'),entry.id);
      await Promise.all([page.waitForNavigation({waitUntil:'networkidle2'}),page.click('.prosody-write')]); await ready();
      assert.equal(await page.$eval('#metre-select',n=>n.value),entry.id);
      assert.equal(await page.$eval('#poem',n=>n.value),draft);
      assert.equal(new URL(page.url()).searchParams.has('metre'),false);
      assert.equal(await page.$eval('#example-dialog',n=>n.open),false);
    }
    console.log('PASS: all 32 browse pages open their own writing mode without losing the draft');
    const counting = ['anushtup','giti','aupachchhandasika','padakulak'];
    for (const entry of entries) {
      await page.select('#metre-select',entry.id);
      const example = entry.draftExample || entry.example;
      await write(example);
      const expected = ['jhyaure','muktachhanda'].includes(entry.id) ? 'guided' : counting.includes(entry.id) ? 'counted' : 'match';
      const statuses = await page.$$eval('.ch-pada',nodes => nodes.map(n=>n.dataset.status));
      assert.ok(statuses.every(status => status===expected),entry.id+': '+statuses.join(','));
      assert.doesNotMatch(await page.$eval('#editor-live-status',n=>n.textContent),/NaN|undefined/);
      if (entry.kind === 'bahr' || ['jhyaure','muktachhanda','anushtup'].includes(entry.id)) {
        assert.equal(await page.$eval('#final-flexible',n=>getComputedStyle(n.closest('label')).display),'none');
      }
      assert.equal(await page.$eval('#analysis-panel > summary',n=>n.textContent),expected==='match'?'लय जाँच्नुहोस्':'गणना हेर्नुहोस्');
    }
    console.log('PASS: all 32 examples get form-appropriate feedback without treating count assistance as full validation');
    await page.select('#metre-select','giti');
    const giti=entries.find(m=>m.id==='giti').example;
    await write(giti+'\n\n'+giti.split('\n')[0]);
    assert.deepEqual(await page.$$eval('.ch-pada',nodes=>nodes.map(n=>n.dataset.status)),['counted','counted','counted']);
    assert.match(await page.$eval('#counts',n=>n.textContent),/१२.*१२/);
    await page.reload({waitUntil:'networkidle2'}); await ready();
    assert.equal(await page.$eval('#metre-select',n=>n.value),'giti');
    assert.equal(await page.$eval('#poem',n=>n.value),giti+'\n\n'+giti.split('\n')[0]);
    await page.select('#metre-select','pramanika');
    await write('नाटिप्नु हेर कोपिला!');
    await page.waitForSelector('.ch-problem-underline');
    await page.select('#metre-select','muktachhanda'); await pause(100);
    assert.equal(await page.$$('.ch-problem-underline').then(nodes=>nodes.length),0);
    console.log('PASS: alternating counts restart after a stanza break, reload retains the selected mode, and free verse clears false errors');
    await page.setViewport({width:375,height:900});
    for (const id of ['mutaqarib_musamman_mahzuf','giti']) {
      await page.select('#metre-select',id);
      await write(entries.find(m=>m.id===id).example);
      await page.$eval('#analysis-panel',n=>{n.open=true;});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
      await page.screenshot({path:'/tmp/writer-'+id+'-mobile.png',fullPage:true});
    }
    await page.evaluate(()=>document.documentElement.setAttribute('data-theme','dark')); await pause(350);
    await page.screenshot({path:'/tmp/writer-expanded-dark.png',fullPage:true});
    assert.deepEqual(errors,[]);
    console.log('PASS: narrow-screen and dark-theme editing without browser errors');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
