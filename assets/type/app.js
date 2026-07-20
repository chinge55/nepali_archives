/* app.js — the /type/ page controller (see roman_nepali_transliteration/plan.md).
 * Loads the engine + data, drives the candidate strip and the editable output.
 * Mobile note: commits are driven by BOTH keydown (desktop) and the input event
 * (Android IMEs often skip/mangle keydown — keyCode 229 — but space still lands
 * in the field, so the input handler catches it). */
import { createEngine } from './engine.js';

const $ = id => document.getElementById(id);
const V = document.currentScript?.dataset?.v || document.querySelector('script[data-v]')?.dataset?.v || '';
const bust = u => V ? `${u}?v=${V}` : u;

const rules = await (await fetch(bust('./rules.json'))).json();
const autocorrect = await (await fetch(bust('./autocorrect.json'))).json();
const engine = createEngine(rules, autocorrect);

const status = t => { $('status').textContent = t; };
try {
  engine.setLexicon(await (await fetch(bust('./lexicon-core.json'))).json());
  status('');
} catch { status('शब्दकोश लोड भएन — नियममा मात्र चल्दैछ'); }
fetch(bust('./lexicon-full.json')).then(r => r.json())
  .then(lx => engine.setLexicon(lx)).catch(() => {});
fetch(bust('./english.json')).then(r => r.json())
  .then(e => engine.setEnglish(e)).catch(() => {});

$('engmode').addEventListener('change', () => { engine.setEnglishFirst($('engmode').checked); render(); });

const history = [];   // flow-typed commits, for backspace-reopen
let cands = [];

// the output is editable only once it holds text — an empty editable box
// invites typing roman in the wrong place (user decision 2026-07-20)
function syncEditable() {
  const out = $('out');
  out.readOnly = out.value === '';
}
$('out').addEventListener('input', syncEditable);
$('out').addEventListener('click', () => { if ($('out').readOnly) $('inp').focus(); });

// trailing punctuation/digits typed with a word ("ho." "1.") map through literals
const LITS = rules.literals || {};
function splitBuffer(v) {
  const m = v.trim().match(/^(.*?)([^a-zA-Z]*)$/);
  const tail = (m[2] || '').split('').map(c => LITS[c] || c).join('');
  return { word: (m[1] || '').trim(), tail };
}

function render() {
  const { word, tail } = splitBuffer($('inp').value);
  cands = word ? engine.candidates(word)
        : tail ? [{ d: tail, src: 'lit' }] : [];   // digits/danda-only buffer
  const box = $('cands');
  box.innerHTML = '';
  cands.forEach((c, i) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'tcand' + (i === 0 ? ' first' : '');
    b.innerHTML = `<span class="n">${i + 1}</span>${c.d}`;
    b.onclick = () => { commit(c.d); $('inp').focus(); };
    box.appendChild(b);
  });
  const rawBuf = $('inp').value.trim();
  if (rawBuf && !cands.some(c => c.d === rawBuf)) {
    const lit = document.createElement('button');
    lit.type = 'button';
    lit.className = 'tcand lit';
    lit.innerHTML = `<span class="n">esc</span>${rawBuf}`;
    lit.onclick = () => { commit(null, undefined, { literal: true }); $('inp').focus(); };
    box.appendChild(lit);
  }
}

// insert at the output's cursor/selection — the no-Devanagari-keyboard fix path:
// select a wrong word in the output, retype it in roman, pick a candidate.
function commit(d, romanOverride, opts = {}) {
  const raw = romanOverride ?? $('inp').value;
  const { tail } = splitBuffer(raw);
  let body;
  if (opts.literal) body = raw.trim();      // esc: exactly as typed
  else if (d) body = d + tail;
  else if (tail) body = tail;               // digits/danda-only buffer
  else return;
  const out = $('out');
  const s = out.selectionStart ?? out.value.length;
  const e = out.selectionEnd ?? out.value.length;
  const atEnd = e === out.value.length && s === e;
  const before = out.value.slice(0, s);
  const sep = (before && !/\s$/.test(before) && s === e) ? ' ' : '';
  const text = sep + body + (atEnd ? ' ' : '');
  out.value = before + text + out.value.slice(e);
  out.selectionStart = out.selectionEnd = s + text.length;
  if (atEnd) out.scrollTop = out.scrollHeight;   // keep the newest text visible
  syncEditable();
  if (atEnd) history.push({ roman: raw.trim(), text }); else history.length = 0;
  if (romanOverride === undefined) $('inp').value = '';
  render();
}

function commitBuffer() {
  const { word, tail } = splitBuffer($('inp').value);
  if (!word && !tail) { $('inp').value = ''; render(); return; }
  commit(word ? (cands.length ? cands[0].d : word) : null);
}

$('inp').addEventListener('input', () => {
  // mobile-safe space/enter commit: whitespace landing in the buffer commits
  // every completed token (also makes pasted phrases convert wholesale)
  const v = $('inp').value;
  if (/\s/.test(v)) {
    const endsOpen = !/\s$/.test(v);
    const parts = v.split(/\s+/).filter(Boolean);
    const rest = endsOpen ? parts.pop() : '';
    for (const w of parts) {
      const { word } = splitBuffer(w);
      commit(word ? (engine.candidates(word)[0]?.d ?? word) : null, w);
    }
    $('inp').value = rest || '';
  }
  render();
});

$('inp').addEventListener('keydown', e => {
  const buf = $('inp').value;
  if ((e.key === ' ' || e.key === 'Enter') && buf.trim()) {
    e.preventDefault();
    commitBuffer();
  } else if (e.key === 'Escape' && buf.trim()) {
    e.preventDefault();
    commit(null, undefined, { literal: true });
  } else if (/^[1-5]$/.test(e.key) && splitBuffer(buf).word && cands[+e.key - 1]) {
    e.preventDefault();
    commit(cands[+e.key - 1].d);
  } else if (e.key === 'Backspace' && !buf && history.length) {
    const out = $('out');
    const last = history[history.length - 1];
    if (out.value.endsWith(last.text)) {          // reopen only if tail unedited
      e.preventDefault();
      history.pop();
      out.value = out.value.slice(0, -last.text.length);
      syncEditable();
      $('inp').value = last.roman || '';
      render();
    }
  }
});

$('copy').addEventListener('click', async () => {
  const { word } = splitBuffer($('inp').value);
  const pending = word ? (cands[0]?.d ?? word) : '';
  const text = ($('out').value + (pending ? ' ' + pending : '')).replace(/\s+$/, '');
  let ok = true;
  try { await navigator.clipboard.writeText(text); }
  catch {
    try { $('out').select(); ok = document.execCommand('copy'); } catch { ok = false; }
  }
  const t = $('toast');
  t.textContent = ok ? 'कपी भयो ✓ Copied' : 'कपी गर्न मिलेन — पाठ select गरेर कपी गर्नुहोस्';
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2200);
});

$('clear').addEventListener('click', () => {
  if ($('out').value && !confirm('सबै मेट्ने? Clear all?')) return;
  history.length = 0; $('out').value = ''; $('inp').value = ''; syncEditable(); render(); $('inp').focus();
});

// keyboard mode: when the on-screen keyboard shrinks the visual viewport,
// compress the page (CSS body.kbd) and pin the tool to the top of what's left,
// so the output, candidates and input are all visible while typing.
if (window.visualViewport) {
  const vv = window.visualViewport;
  let t = 0;
  const sync = () => {
    const kbd = vv.height < window.innerHeight * 0.8;
    if (document.body.classList.toggle('kbd', kbd) || kbd) {
      clearTimeout(t);
      t = setTimeout(() => {
        if (document.body.classList.contains('kbd')) {
          window.scrollTo({ top: $('out').getBoundingClientRect().top + window.scrollY - vv.offsetTop - 4 });
        }
      }, 60);
    }
  };
  vv.addEventListener('resize', sync);
  $('inp').addEventListener('focus', () => setTimeout(sync, 350));
}

render();
if (matchMedia('(hover: hover)').matches) $('inp').focus();  // don't pop the keyboard on phones
