/* engine.js — Roman→Devanagari POC engine (Stage 2, plan.md).
 *
 * Layers (literature_review.md §2): rule fan-out (1+2) → normalized lexicon
 * lookup + frequency rank (3) → literal pass-through (4). Bigram re-rank and
 * selection learning are Stage 4. Pure ES module, no dependencies.
 *
 * normalize() MUST stay in sync with pipeline/translit_keys.py — the Python
 * test file is the spec.
 */

// ---- normalization (port of translit_keys.normalize) ----------------------
const SUB = [
  ['ksh', 'kC'], ['chh', 'C'], ['ch', 'C'], ['gy', 'J'], ['sh', 's'],
  ['ph', 'P'], ['ee', 'i'], ['oo', 'u'],
  ['c', 'C'], ['x', 'C'], ['f', 'P'], ['z', 'j'], ['w', 'b'], ['v', 'b'], ['q', 'k'],
];
const SUB_MAP = Object.fromEntries(SUB);
const SUB_RE = new RegExp(SUB.map(([k]) => k).sort((a, b) => b.length - a.length).join('|'), 'g');

export function normalize(s) {
  s = s.toLowerCase().replace(/[^a-z]+/g, ' ').trim();
  if (!s) return '';
  return s.split(/ +/).map(w => {
    w = w.replace(SUB_RE, m => SUB_MAP[m]);
    w = w.replace(/(.)\1+/g, '$1');
    if (w.length > 1 && w.endsWith('a')) w = w.slice(0, -1);
    return w;
  }).join(' ');
}

// ---- rule layer: greedy-fanout token DP ------------------------------------
const VIRAMA = '्';
const SIGNS = new Set(['ं', 'ँ']); // ं ँ attach without virama

export function ruleCandidates(word, rules, topN = 6, beam = 12) {
  // case-aware: uppercase retroflex/sibilant hints (T->ट, D->ड, N->ण, S->ष)
  // match exact-case tokens first, then fall back to lowercase.
  const cons = rules.consonants, vows = rules.vowels, lits = rules.literals || {};
  const lookup = (table, sub) => table[sub] || table[sub.toLowerCase()];
  const maxTok = 3;
  // states[i] = [{out, cost, cons:boolean}]
  const states = Array.from({ length: word.length + 1 }, () => []);
  states[0].push({ out: '', cost: 0, cons: false });
  for (let i = 0; i < word.length; i++) {
    if (!states[i].length) continue;
    prune(states[i], beam);
    for (const st of states[i]) {
      let matched = false;
      for (let L = Math.min(maxTok, word.length - i); L >= 1; L--) {
        const sub = word.slice(i, i + L);
        const bonus = -0.15 * (L - 1);   // prefer digraph tokens over char splits (bh > b+h)
        const vEnt = lookup(vows, sub), cEnt = lookup(cons, sub);
        if (vEnt) {
          matched = true;
          if (sub === 'a' && i + L === word.length && st.cons) {
            // word-final 'a' after a consonant: typists who mean bare ल omit the
            // a entirely, so the ा reading wins (bhetaula -> भेटौला over भेटौल)
            states[i + L].push({ out: st.out + 'ा', cost: st.cost + 0.5, cons: false });
            states[i + L].push({ out: st.out, cost: st.cost + 0.75, cons: false });
          } else {
            for (const [ind, mat, c] of vEnt) {
              states[i + L].push({ out: st.out + (st.cons ? mat : ind), cost: st.cost + c + bonus, cons: false });
            }
          }
        }
        if (cEnt) {
          matched = true;
          for (const [d, c] of cEnt) {
            if (SIGNS.has(d)) {
              if (st.out) states[i + L].push({ out: st.out + d, cost: st.cost + c + bonus, cons: false });
            } else {
              states[i + L].push({ out: st.out + (st.cons ? VIRAMA : '') + d, cost: st.cost + c + bonus, cons: true });
            }
          }
        }
      }
      if (!matched) { // unknown char: literal map or pass through
        const ch = word[i].toLowerCase();
        states[i + 1].push({ out: st.out + (lits[ch] || ch), cost: st.cost + 3, cons: false });
      }
    }
  }
  const finals = [];
  for (const st of states[word.length]) {
    finals.push({ out: st.out, cost: st.cost });
    if (st.cons) finals.push({ out: st.out + VIRAMA, cost: st.cost + 1.5 }); // गर्छन् variant
  }
  prune(finals, 50);
  const seen = new Set(), out = [];
  for (const f of finals) {
    if (!seen.has(f.out)) { seen.add(f.out); out.push(f.out); }
    if (out.length >= topN) break;
  }
  return out;
}

function prune(arr, n) {
  arr.sort((a, b) => a.cost - b.cost);
  const seen = new Set();
  let w = 0;
  for (const st of arr) {
    const k = st.out + '|' + st.cons;
    if (seen.has(k)) continue;
    seen.add(k);
    arr[w++] = st;
    if (w >= n) break;
  }
  arr.length = w;
}

// ---- engine ----------------------------------------------------------------
export function createEngine(rules, autocorrect = {}, english = null) {
  let lexicon = null; // {words: [[deva, canon, score]...], keys: {key: [idx...]}}
  const ac = autocorrect.map || {};
  let engSet = english instanceof Set ? english : new Set(english?.words || []);
  let englishFirst = true; // default: english stays english (user decision 2026-07-20)

  function setLexicon(lx) {
    if (!lexicon || lx.words.length >= lexicon.words.length) lexicon = lx;
  }

  /** top candidates for a roman buffer: [{d, src}] best-first */
  function candidates(buffer, topN = 5) {
    const cased = buffer.replace(/[^a-zA-Z]/g, '');
    const raw = cased.toLowerCase();
    if (!raw) return [];
    const out = [], seen = new Set();
    const push = (d, src) => {
      if (d && !seen.has(d)) { seen.add(d); out.push({ d, src }); }
    };
    const key = normalize(raw);
    if (englishFirst && engSet.has(raw)) push(raw, 'eng'); // english stays english
    if (ac[key]) push(ac[key], 'ac');
    if (lexicon) {
      const idxs = lexicon.keys[key] || [];
      const entries = idxs.map(i => lexicon.words[i]);
      // exact-surface bonus: the user's raw string matching the canonical
      // romanization outranks pure frequency order
      entries.sort((a, b) => (a[1] === raw ? -1 : 0) - (b[1] === raw ? -1 : 0));
      for (const [deva] of entries) push(deva, 'lex');
    }
    for (const d of ruleCandidates(cased, rules)) push(d, 'rule');
    return out.slice(0, topN);
  }

  const setEnglish = lst => { engSet = lst instanceof Set ? lst : new Set(lst?.words || []); };
  const setEnglishFirst = v => { englishFirst = !!v; };
  return { candidates, setLexicon, setEnglish, setEnglishFirst, normalize,
           get lexiconSize() { return lexicon ? lexicon.words.length : 0; } };
}
