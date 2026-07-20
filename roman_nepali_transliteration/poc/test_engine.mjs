// test_engine.mjs — engine smoke test + JS/Python normalize parity.
// Run: node poc/test_engine.mjs   (after build_lexicon.py)
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createEngine, normalize, romanize } from '../../assets/type/engine.js';

const here = new URL('.', import.meta.url).pathname;
const A = here + '../../assets/type/';
const rules = JSON.parse(readFileSync(A + 'rules.json', 'utf8'));
const autocorrect = JSON.parse(readFileSync(A + 'autocorrect.json', 'utf8'));
const english = JSON.parse(readFileSync(A + 'english.json', 'utf8'));
const engine = createEngine(rules, autocorrect, english);
engine.setLexicon(JSON.parse(readFileSync(A + 'lexicon-full.json', 'utf8')));

// 1. normalize parity with the Python spec
const words = ['naam', 'chha', 'xa', 'gyaan', 'kasTo', 'hunchha', 'prithvi',
               'devkota', 'laxmi', 'sangai', 'basanta', 'pherii', 'saathee', 'wakil'];
const py = execFileSync('python3', ['-c', `
import sys; sys.path.insert(0, ${JSON.stringify(here + '../pipeline')})
from translit_keys import normalize
for w in ${JSON.stringify(words)}: print(normalize(w))
`]).toString().trim().split('\n');
let bad = 0;
words.forEach((w, i) => {
  if (normalize(w) !== py[i]) { console.error(`parity FAIL ${w}: js=${normalize(w)} py=${py[i]}`); bad++; }
});

// 1b. reverse-romanizer parity with Python key_romanize (feeds backspace-reopen)
const rwords = ['नाम','सँगै','वसन्त','देवकोटा','पागल','गर्छन्','क्षमा','ज्ञान','हुन्छ','राम्रो','लक्ष्मी','काठमाडौं','पृथ्वी','सम्झना'];
const rpy = execFileSync('python3', ['-c', `
import sys; sys.path.insert(0, ${JSON.stringify(here + '../pipeline')})
from translit_keys import key_romanize
for w in ${JSON.stringify(rwords)}: print(key_romanize(w))
`]).toString().trim().split('\n');
rwords.forEach((w, i) => {
  if (romanize(w) !== rpy[i]) { console.error(`romanize parity FAIL ${w}: js=${romanize(w)} py=${rpy[i]}`); bad++; }
});

// 2. top-1 expectations (the "path exists" sanity set)
const TOP1 = {
  mero: 'मेरो', naam: 'नाम', ho: 'हो', chha: 'छ', xa: 'छ',
  nepali: 'नेपाली', muna: 'मुना', madan: 'मदन', pagal: 'पागल',
  devkota: 'देवकोटा', nepal: 'नेपाल', garchha: 'गर्छ', hunchha: 'हुन्छ',
  sangai: 'सँगै', timro: 'तिम्रो', kavita: 'कविता', kathmandu: 'काठमाडौं',
};
const TOP5 = { laxmi: 'लक्ष्मी', yatri: 'यात्री', basanta: 'वसन्त', bholi: 'भोलि', ma: 'म' };
for (const [inp, want] of Object.entries(TOP1)) {
  const got = engine.candidates(inp);
  if (!got.length || got[0].d !== want) {
    console.error(`top1 FAIL ${inp}: want ${want}, got [${got.map(c => c.d).join(' ')}]`);
    bad++;
  }
}
for (const [inp, want] of Object.entries(TOP5)) {
  const got = engine.candidates(inp).map(c => c.d);
  if (!got.includes(want)) {
    console.error(`top5 FAIL ${inp}: want ${want} in [${got.join(' ')}]`);
    bad++;
  }
}

// 2b. english pass-through (default ON) + toggle + case hints
for (const w of ['school', 'reply', 'sms', 'ok']) {
  const got = engine.candidates(w);
  if (!got.length || got[0].d !== w || got[0].src !== 'eng') {
    console.error(`eng FAIL ${w}: got [${got.map(c => c.d).join(' ')}]`); bad++;
  }
}
{ const got = engine.candidates('man');  // collides with mann/मन -> nepali first
  if (!got.length || got[0].d !== 'मन') { console.error(`eng-collision FAIL man: [${got.map(c=>c.d).join(' ')}]`); bad++; } }
engine.setEnglishFirst(false);
{ const got = engine.candidates('school');
  if (got.length && got[0].d === 'school') { console.error('toggle FAIL: still english-first when off'); bad++; } }
engine.setEnglishFirst(true);
{ const got = engine.candidates('bheTaula');  // uppercase retroflex hint
  if (!got.some(c => c.d === 'भेटौला')) { console.error(`caseHint FAIL bheTaula: [${got.map(c=>c.d).join(' ')}]`); bad++; }
  else console.log('bheTaula ->', got.map(c => c.d).join(' ')); }

// 3. rules-only fallback (OOV must never fail closed)
const oov = engine.candidates('gajakaputra');
if (!oov.length) { console.error('OOV FAIL: no candidates'); bad++; }
console.log('OOV sample gajakaputra ->', oov.map(c => c.d).join(' '));

// 4. latency: 2000 lookups on a mixed set
const mix = [...Object.keys(TOP1), 'timilai', 'ramro', 'aaja', 'mausam'];
const t0 = performance.now();
for (let i = 0; i < 2000; i++) engine.candidates(mix[i % mix.length]);
const ms = (performance.now() - t0) / 2000;
console.log(`latency: ${ms.toFixed(3)} ms/lookup (budget <10)`);
if (ms > 10) { console.error('latency FAIL'); bad++; }

if (bad) { console.error(`\n${bad} failures`); process.exit(1); }
console.log(`OK: parity ${words.length}, top1 ${Object.keys(TOP1).length}, top5 ${Object.keys(TOP5).length}, lexicon ${engine.lexiconSize}`);
