/* app.js — the /type/ page controller (see roman_nepali_transliteration/plan.md).
 * Loads the engine + data, drives the candidate strip and the editable output.
 * Mobile note: commits are driven by BOTH keydown (desktop) and the input event
 * (Android IMEs often skip/mangle keydown — keyCode 229 — but space still lands
 * in the field, so the input handler catches it). */
import { createEngine, romanize } from './engine.js';

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

// highlight of the word being re-edited (backspace-reopen): a backdrop layer
// mirrors the textarea text and marks the range in the accent colour
const escHtml = t => t.replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
let hlRange = null;   // [start, end] of the word being re-edited
function setHighlight(start, end) {
  const out = $('out'), bg = $('outbg');
  if (start == null || start >= end) { bg.innerHTML = ''; hlRange = null; return; }
  hlRange = [start, end];
  const v = out.value;
  bg.innerHTML = escHtml(v.slice(0, start)) + '<mark>' + escHtml(v.slice(start, end)) + '</mark>' + escHtml(v.slice(end));
  bg.scrollTop = out.scrollTop;
}
$('out').addEventListener('scroll', () => { $('outbg').scrollTop = $('out').scrollTop; });
$('out').addEventListener('input', () => setHighlight(null));

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
  setHighlight(null);
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
  } else if (e.key === 'Backspace' && !buf) {
    const out = $('out');
    if (!out.value.trim()) return;
    e.preventDefault();
    if (hlRange) {
      // second backspace on an already-highlighted word: delete it entirely
      const [hs, he] = hlRange;
      const after = out.value.slice(he).replace(/^ /, '');
      out.value = out.value.slice(0, hs) + after;
      out.setSelectionRange(hs, hs);
      setHighlight(null);
      syncEditable();
      render();
      return;
    }
    // reopen the LAST word of the output — works for anything already written
    // (flow-typed, hand-edited or pasted): highlight + select it, put its roman
    // back in the input; the session history supplies the exact roman when the
    // tail is untouched, the reverse romanizer covers everything else.
    const m = out.value.match(/(\S+)(\s*)$/);
    if (!m) return;
    const start = m.index, end = start + m[1].length;
    let roman = null;
    const last = history[history.length - 1];
    if (last && out.value.endsWith(last.text) && last.roman) {
      history.pop();
      roman = last.roman;
    } else {
      history.length = 0;
      roman = romanize(m[1]);
    }
    out.setSelectionRange(start, end);
    out.scrollTop = out.scrollHeight;
    setHighlight(start, end);
    $('inp').value = roman || '';
    render();
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
  history.length = 0; $('out').value = ''; $('inp').value = ''; setHighlight(null); syncEditable(); render(); $('inp').focus();
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
