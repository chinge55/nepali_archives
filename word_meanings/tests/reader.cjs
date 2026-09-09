const puppeteer = require('puppeteer');
const fs = require('fs');
const assert = require('assert/strict');
const base = (process.env.PREVIEW_URL || 'http://localhost:8258/').replace(/\/?$/, '/');
const path = require('path');
const output = path.resolve(__dirname, '../data/qa');
fs.mkdirSync(output, {recursive:true});
const canonical = fs.readFileSync(path.resolve(__dirname, '../../archives/authors/devkota/munamadan/text.txt'),'utf8');
const results=[];
const check=(ok,label)=>{assert(ok,label);results.push(label);console.log(label)};
(async()=>{
 const browser=await puppeteer.launch({headless:'new',args:['--no-sandbox']});
 try {
  for(const width of [375,1280]) {
   const page=await browser.newPage(); const errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   await page.setViewport({width,height:900});
   await page.goto(base,{waitUntil:'networkidle0'});
   await page.waitForSelector('.original-text');
   check(await page.$eval('.original-text',e=>e.textContent)===canonical,`${width}: original text exact`);
   check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${width}: no horizontal overflow`);
   // Native single-word selection deep enough to require a viewport-reachable action.
   await page.evaluate(()=>{
    const node=document.querySelector('.original-text').firstChild;
    const start=node.textContent.indexOf('कल्पने माली, अम्लान कुसुम,')+'कल्पने माली, अम्लान '.length;
    const r=document.createRange();r.setStart(node,start);r.setEnd(node,start+'कुसुम'.length);
    getSelection().removeAllRanges();getSelection().addRange(r);
    const rect=r.getBoundingClientRect();scrollTo(0,scrollY+rect.top-200);
   });
   await page.waitForFunction(()=>!document.querySelector('#selectionLookup').disabled);
   const before=await page.evaluate(()=>scrollY);
   check(await page.$eval('#selectionLookup',e=>{const r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight;}),`${width}: selection action reachable`);
   await page.click('#selectionLookup');
   check(await page.$eval('#meaningCard .context-quote',e=>e.textContent)==='कल्पने माली, अम्लान कुसुम,',`${width}: exact selected line quoted`);
   check((await page.$eval('#meaningCard .sense-list',e=>e.textContent)).includes('फूल; पुष्प'),`${width}: reviewed sense first`);
   check(await page.$eval('#meaningCard details',e=>!e.open),`${width}: other senses collapsed`);
   check(await page.$eval('#meaningCard',e=>e.getAttribute('aria-modal'))===String(width===375),`${width}: modal semantics`);
   await page.click('#saveWord');
   check(await page.evaluate(()=>document.activeElement.id)==='saveWord',`${width}: save retains button focus`);
   check(await page.$eval('#meaningCard .context-quote',e=>e.textContent)==='कल्पने माली, अम्लान कुसुम,',`${width}: save retains context`);
   check(await page.evaluate(()=>JSON.parse(localStorage.getItem('nepali-word-collection')).includes('कुसुम')),`${width}: word saved`);
   if(width===375){
    await page.focus('#closeMeaning');await page.keyboard.down('Shift');await page.keyboard.press('Tab');await page.keyboard.up('Shift');
    check(await page.evaluate(()=>document.querySelector('#meaningCard').contains(document.activeElement)),`${width}: focus contained`);
   }
   await page.keyboard.press('Escape');
   check(Math.abs(await page.evaluate(()=>scrollY)-before)<2,`${width}: original scroll retained`);
   check(await page.evaluate(()=>document.activeElement.id)==='textColumn',`${width}: reading focus restored`);
   // Generic typed lookup never claims a contextual interpretation.
   await page.$eval('#lookupInput',e=>{document.querySelector('#lookupTools').open=true;e.value='कुसुम';document.querySelector('#lookupForm').requestSubmit();});
   check(await page.$$eval('#meaningCard > .sense-group .sense-list > li',nodes=>nodes.length)<=2,`${width}: generic panel shows at most two senses initially`);
   check(await page.$eval('#meaningCard .source-options',e=>!e.open),`${width}: secondary sources collapsed`);
   check(!(await page.$('#meaningCard .context-quote')),`${width}: generic lookup has no invented passage`);
   check(await page.$$eval('#meaningCard a',nodes=>nodes.every(e=>e.href.startsWith('https://'))),`${width}: valid source URLs`);
   check(!(await page.$eval('#meaningCard',e=>/undefined|\[object Object\]/.test(e.textContent))),`${width}: no malformed rendered data`);
   await page.keyboard.press('Escape');
   await page.$eval('#lookupInput',e=>{document.querySelector('#lookupTools').open=true;e.value='अर्थनभेटिएकोशब्द';document.querySelector('#lookupForm').requestSubmit();});
   check(!!await page.$('.unavailable'),`${width}: unknown word handled`);
   check(await page.$eval('#meaningCard',e=>e.getAttribute('aria-modal'))===String(width===375),`${width}: unknown dialog accessible`);
   await page.keyboard.press('Escape');
   await page.reload({waitUntil:'networkidle0'});await page.waitForSelector('.original-text');
   check(await page.$eval('#collectionCount',e=>e.textContent)==='१',`${width}: saved word survives reload`);
   await page.click('#collectionToggle');await page.focus('#closeCollection');
   await page.keyboard.down('Shift');await page.keyboard.press('Tab');await page.keyboard.up('Shift');
   check(await page.evaluate(()=>document.querySelector('#collection').contains(document.activeElement)),`${width}: collection focus contained`);
   await page.click('#clearCollection');check(await page.$eval('#collectionCount',e=>e.textContent)==='०',`${width}: collection clears`);
   await page.keyboard.press('Escape');
   await page.evaluate(()=>localStorage.setItem('nepali-word-collection',JSON.stringify(['<img onerror=alert(1)>','__proto__','कुसुम','कुसुम',8])));
   await page.reload({waitUntil:'networkidle0'});await page.waitForSelector('.original-text');
   check(await page.$eval('#collectionCount',e=>e.textContent)==='१',`${width}: malformed saved entries filtered`);
   await page.evaluate(()=>{localStorage.clear();Storage.prototype.setItem=function(){throw Error('denied')}});
   await page.$eval('#lookupInput',e=>{document.querySelector('#lookupTools').open=true;e.value='अम्लान';document.querySelector('#lookupForm').requestSubmit();});
   await page.click('#saveWord');check((await page.$eval('.storage-status',e=>e.textContent)).includes('सकिएन'),`${width}: storage failure visible`);
   await page.keyboard.press('Escape');
   // Final screenshot shows selected contextual meaning at its source passage.
   await page.evaluate(()=>{
    const n=document.querySelector('.original-text').firstChild,s=n.textContent.indexOf('कल्पने माली, अम्लान कुसुम,')+12;
    const start=n.textContent.indexOf('कुसुम',n.textContent.indexOf('कल्पने माली,'));
    const r=document.createRange();r.setStart(n,start);r.setEnd(n,start+5);getSelection().removeAllRanges();getSelection().addRange(r);
    scrollTo(0,scrollY+r.getBoundingClientRect().top-160);
   });
   await page.waitForFunction(()=>!document.querySelector('#selectionLookup').disabled);await page.click('#selectionLookup');
   await page.screenshot({path:path.join(output, `reader-${width}.png`)});
   if(width===1280){
    await page.evaluate(()=>{const n=document.querySelector('.original-text').firstChild;const start=n.textContent.indexOf('अम्लान');const r=document.createRange();r.setStart(n,start);r.setEnd(n,start+'अम्लान'.length);getSelection().removeAllRanges();getSelection().addRange(r)});
    await page.waitForFunction(()=>!document.querySelector('#selectionLookup').disabled);await page.click('#selectionLookup');
    check(await page.$eval('#meaningCard h2',e=>e.textContent)==='अम्लान','desktop: next word opens without closing current meaning');
   }
   check(!errors.length,`${width}: no JavaScript errors`);await page.close();
  }
  const failed=await browser.newPage();await failed.setRequestInterception(true);
  failed.on('request',req=>req.url().endsWith('/work.json')?req.abort():req.continue());
  await failed.goto(base,{waitUntil:'networkidle0'});
  check(await failed.$eval('#loadError',e=>!e.hidden),'fetch failure visible');
  check(await failed.$eval('#textLink',e=>e.getAttribute('href'))==='text.txt','TXT fallback on failure');
  check(await failed.$eval('.original-text',e=>e.textContent)===canonical,'dictionary failure preserves complete readable text');
  await failed.setJavaScriptEnabled(false);await failed.goto(base);check(await failed.$eval('.original-text',e=>e.textContent)===canonical,'complete text readable without JavaScript');
  await failed.close();
  const report=JSON.stringify({passed:results.length,checks:results},null,2);
  fs.writeFileSync(path.join(output,'browser-check.json'),report+'\n');
  console.log(report);
 } finally {await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
