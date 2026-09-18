/* app.js — the /type/ page controller (see roman_nepali_transliteration/plan.md).
 * Loads the engine + data, drives the candidate strip and the editable output.
 * Mobile note: commits are driven by BOTH keydown (desktop) and the input event
 * (Android IMEs often skip/mangle keydown — keyCode 229 — but space still lands
 * in the field, so the input handler catches it). */
let createEngine, romanize;

const $ = id => document.getElementById(id);
const V = document.currentScript?.dataset?.v || document.querySelector('script[data-v]')?.dataset?.v || '';
const bust = u => V ? `${u}?v=${V}` : u;

let engine = null;
let rules = { literals: {} };
let loading = false, composing = false, loadAttempt = 0;
const notices = {};
function notice(key, text) { notices[key] = text; status(Object.values(notices).filter(Boolean).join(" ")); }
const status = t => { $('status').textContent = t; };
async function json(name) {
  const response = await fetch(bust(`./${name}.json`));
  if (!response.ok) throw new Error(`Could not load ${name}`);
  return response.json();
}
async function load() {
  if (loading) return;
  loading = true;
  $('retry').hidden = true;
  status('तयार हुँदैछ… Loading; you can start typing.');
  try {
    if (!createEngine) {
      const moduleURL = `${bust('./engine.js')}${V ? '&' : '?'}attempt=${loadAttempt++}`;
      ({ createEngine, romanize } = await import(moduleURL));
    }
    rules = await json('rules');
    let autocorrect = {};
    try { autocorrect = await json('autocorrect'); } catch { /* Rules still work. */ }
    engine = createEngine(rules, autocorrect);
    engine.setEnglishFirst($('engmode').checked);
    notice('dictionary', 'शब्दकोश लोड हुँदैछ… Loading dictionary.');
    $('type-tool').dataset.ready = 'true';
    if (!composing && /\s/.test($('inp').value)) { remember(); processInput(); }
    render();
    // Input handlers already work while the larger dictionaries load.
    json('lexicon-core').then(lx => {
      engine.setLexicon(lx); notice('dictionary', ''); render();
    }).catch(() => { if (!engine.lexiconSize) notice('dictionary', 'शब्दकोश लोड भएन — नियममा मात्र चल्दैछ। Dictionary unavailable; basic typing works.'); });
    json('lexicon-full').then(lx => { engine.setLexicon(lx); notice('dictionary', ''); render(); }).catch(() => {});
    json('english').then(words => { engine.setEnglish(words); render(); }).catch(() => {
      notice('english', 'English शब्दकोश लोड भएन — जस्ताको तस्तै राख्ने विकल्प प्रयोग गर्नुहोस्। Use “Keep as typed” for English.');
    });
  } catch {
    status('टाइप गर्ने नियम लोड भएन। लेखेको पाठ सुरक्षित छ — फेरि प्रयास गर्नुहोस्। Could not load typing tool.');
    $('retry').hidden = false;
  } finally { loading = false; render(); }
}
$('retry').addEventListener('click', load);

$('engmode').addEventListener('change', () => {
  remember('action', { mode: !$('engmode').checked });
  engine?.setEnglishFirst($('engmode').checked); changed(); render();
});

const history = [];   // flow-typed commits, for backspace-reopen
let cands = [];

// A draft is local to this browser. Storage failure never disables typing.
const DRAFT_KEY = 'nepaliarchives:type:draft:v1';
const undoStack = [], redoStack = [];
let editable = false, saveTimer, lastEdit = '', lastEditAt = 0;
function snapshot() {
  const out = $('out');
  return { output: out.value, pending: $('inp').value, mode: $('engmode').checked,
    start: out.selectionStart, end: out.selectionEnd, editable,
    highlight: hlRange, words: history.slice(-100) };
}
function remember(kind = 'action', overrides = {}) {
  const now = Date.now();
  if (kind !== lastEdit || kind === 'action' || now - lastEditAt > 700) {
    undoStack.push({ ...snapshot(), ...overrides });
    if (undoStack.length > 100) undoStack.shift();
  }
  lastEdit = kind; lastEditAt = now; redoStack.length = 0;
}
function historyButtons() {
  $('undo').disabled = !undoStack.length;
  $('redo').disabled = !redoStack.length;
}
function saveDraft() {
  clearTimeout(saveTimer);
  try {
    const state = snapshot();
    if (state.output || state.pending) {
      localStorage.setItem(DRAFT_KEY, JSON.stringify({ version: 1, ...state }));
      $('draftstatus').textContent = 'यस ब्राउजरमा सुरक्षित · Saved in this browser';
    } else {
      localStorage.removeItem(DRAFT_KEY);
      $('draftstatus').textContent = '';
    }
  } catch {
    $('draftstatus').textContent = 'पाठ सुरक्षित गर्न सकिएन — बन्द गर्नुअघि कपी गर्नुहोस्। Draft saving unavailable; copy before leaving.';
  }
}
function changed() {
  historyButtons();
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveDraft, 250);
}
function restore(state) {
  $('out').value = state.output;
  $('inp').value = state.pending;
  $('engmode').checked = state.mode;
  editable = !!state.editable || !!state.output;
  const start = Number.isInteger(state.start) ? state.start : state.output.length;
  const end = Number.isInteger(state.end) ? state.end : start;
  $('out').setSelectionRange(start, end);
  history.length = 0;
  if (Array.isArray(state.words)) history.push(...state.words.slice(-100).filter(w =>
    w && typeof w.roman === 'string' && typeof w.text === 'string'));
  setHighlight(null);
  if (Array.isArray(state.highlight) && state.highlight.length === 2 &&
      state.highlight.every(Number.isInteger)) setHighlight(...state.highlight);
  engine?.setEnglishFirst(state.mode);
  syncEditable(); render(); historyButtons();
}
function restoreDraft() {
  try {
    const state = JSON.parse(localStorage.getItem(DRAFT_KEY));
    if (state?.version === 1 && typeof state.output === 'string' &&
        typeof state.pending === 'string' && typeof state.mode === 'boolean') {
      restore(state);
      $('draftstatus').textContent = 'अघिल्लो पाठ फर्काइयो · Draft restored';
    }
  } catch {
    $('draftstatus').textContent = 'अघिल्लो पाठ खोल्न सकिएन · Draft could not be restored';
  }
}
function travel(from, to) {
  if (!from.length) return;
  to.push(snapshot());
  restore(from.pop());
  lastEdit = ''; changed(); saveDraft();
}
$('undo').addEventListener('click', () => travel(undoStack, redoStack));
$('redo').addEventListener('click', () => travel(redoStack, undoStack));
for (const field of [$('inp'), $('out')]) {
  field.addEventListener('beforeinput', e => {
    if (e.inputType === 'historyUndo' || e.inputType === 'historyRedo') {
      e.preventDefault();
      if (e.inputType === 'historyUndo') travel(undoStack, redoStack);
      else travel(redoStack, undoStack);
    } else {
      const kind = e.inputType || 'edit';
      remember(kind === 'insertFromPaste' || (e.data?.length > 1 && !e.isComposing) ? 'action' : `${field.id}:${kind}`);
    }
  });
  field.addEventListener('keydown', e => {
    if (e.isComposing || !(e.ctrlKey || e.metaKey) || e.altKey) return;
    const key = e.key.toLowerCase();
    if (key === 'z' || key === 'y') {
      e.preventDefault();
      if (key === 'y' || e.shiftKey) travel(redoStack, undoStack);
      else travel(undoStack, redoStack);
    }
  });
}
window.addEventListener('pagehide', saveDraft);
document.addEventListener('visibilitychange', () => { if (document.hidden) saveDraft(); });

// Initially guide Roman input to the composer. Once editing starts, deleting
// everything must not unexpectedly lock the output again.
function syncEditable() {
  if ($('out').value) editable = true;
  $('out').readOnly = !editable;
}
$('out').addEventListener('input', () => {
  history.length = 0; syncEditable(); changed(); render();
});
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

// Convert ordinary words and their boundary punctuation. Preserve structured
// Latin tokens (email, URL, mixed letters/digits) exactly, rather than guessing.
function choices(raw) {
  raw = raw.trim();
  if (!raw) return [];
  const literal = value => value.replace(/[0-9.|]/g, c => rules.literals[c] || c);
  if (/^\d+(?:[.,:/-]\d+)*$/.test(raw)) {
    return [{ d: raw.replace(/[0-9]/g, c => rules.literals[c] || c), src: 'lit' }];
  }
  const word = raw.match(/^([("'“‘]*)([a-zA-Z]+)([)"'”’.,!?;:|…]*)$/);
  if (word) return engine.candidates(word[2]).map(c => ({ ...c, d: word[1] + c.d + literal(word[3]) }));
  return [{ d: /[a-zA-Z]/.test(raw) ? raw : literal(raw), src: 'lit' }];
}
function render() {
  cands = engine && !composing ? choices($('inp').value) : [];
  $('copy').disabled = composing || (!engine && !!$('inp').value.trim()) || (!$('inp').value.trim() && !$('out').value);
  $('paragraph').disabled = composing || (!engine && !!$('inp').value);
  const box = $('cands');
  const focused = box.contains(document.activeElement) ? document.activeElement?.dataset.value : null;
  box.replaceChildren();
  const add = (text, shortcut, cls, choose) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = cls;
    button.dataset.value = text;
    button.setAttribute('aria-label', `${text} · ${shortcut}`);
    button.title = text;
    const hint = document.createElement('span');
    hint.className = 'n';
    hint.textContent = shortcut;
    button.append(hint, document.createTextNode(text));
    button.onclick = () => { remember(); choose(); $('inp').focus(); };
    box.appendChild(button);
  };
  cands.forEach((c, i) => add(c.d, `Alt+${i + 1}`, 'tcand' + (i === 0 ? ' first' : ''), () => commit(c.d)));
  const raw = $('inp').value.trim();
  if (engine && !composing && raw && !cands.some(c => c.d === raw)) {
    add(raw, 'जस्ताको तस्तै · Keep as typed', 'tcand lit', () => commit(raw));
  }
  if (!box.childElementCount) {
    const hint = document.createElement('span');
    hint.className = 'candidate-empty';
    hint.textContent = 'शब्दका विकल्प यहाँ देखिन्छन् · Suggestions';
    box.appendChild(hint);
  }
  if (focused !== null) {
    const target = [...box.querySelectorAll('button')].find(b => b.dataset.value === focused);
    (target || $('inp')).focus({ preventScroll: true });
  }
  clearTimeout(announceTimer);
  announceTimer = setTimeout(() => {
    $('suggestionstatus').textContent = cands.length
      ? `${cands.length} विकल्प। पहिलो: ${cands[0].d}। Space ले रोज्नुहोस्।` : '';
  }, 400);
}
let announceTimer;
$('cands').addEventListener('keydown', e => {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
  const buttons = [...$('cands').querySelectorAll('button')];
  const at = buttons.indexOf(document.activeElement);
  if (at < 0) return;
  e.preventDefault();
  const index = e.key === 'Home' ? 0 : e.key === 'End' ? buttons.length - 1
    : Math.max(0, Math.min(buttons.length - 1, at + (e.key === 'ArrowRight' ? 1 : -1)));
  buttons[index].focus();
});

// insert at the output's cursor/selection — the no-Devanagari-keyboard fix path:
// select a wrong word in the output, retype it in roman, pick a candidate.
function commit(d, romanOverride, opts = {}) {
  const raw = romanOverride ?? $('inp').value;
  const body = opts.literal ? raw.trim() : d;
  if (!body) return;
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
  if (atEnd) { history.push({ roman: raw.trim(), text }); if (history.length > 100) history.shift(); }
  else history.length = 0;
  if (romanOverride === undefined) $('inp').value = '';
  changed(); render();
}

function commitBuffer() {
  if (!engine || composing) return;
  if (/\s/.test($('inp').value.trim())) processInput();
  commit(cands[0]?.d ?? $('inp').value.trim());
}
function insertBreak(separator = '\n') {
  const out = $('out');
  const before = out.value.slice(0, out.selectionStart).replace(/[ \t]+$/, '');
  const after = out.value.slice(out.selectionEnd);
  out.value = before + separator + after;
  out.setSelectionRange(before.length + separator.length, before.length + separator.length);
  history.length = 0; setHighlight(null); syncEditable(); changed(); render();
}
function processInput() {
  if (!engine) { changed(); return; } // Preserve early input until ready.
  const v = $('inp').value.replace(/\r\n?/g, '\n');
  if (/\s/.test(v)) {
    const parts = v.split(/(\s+)/);
    for (let i = 0; i < parts.length - 1; i += 2) {
      if (parts[i]) commit(choices(parts[i])[0]?.d ?? parts[i], parts[i]);
      const breaks = parts[i + 1].replace(/[^\n]/g, '');
      if (breaks) insertBreak(breaks);
    }
    $('inp').value = parts[parts.length - 1];
  }
  changed(); render();
}
$('paragraph').addEventListener('click', () => {
  if (composing || (!engine && $('inp').value)) return;
  remember(); commitBuffer(); insertBreak('\n\n'); $('inp').focus();
});
$('inp').addEventListener('input', e => { if (!e.isComposing) processInput(); });
$('inp').addEventListener('compositionstart', () => { composing = true; render(); });
$('inp').addEventListener('compositionend', () => { composing = false; processInput(); });

$('inp').addEventListener('keydown', e => {
  const buf = $('inp').value;
  if (!engine || composing || e.isComposing || e.keyCode === 229) return;
  if (e.key === 'Enter') {
    e.preventDefault(); remember(); commitBuffer(); insertBreak(e.shiftKey ? '\n\n' : '\n');
  } else if (e.key === ' ' && buf.trim()) {
    e.preventDefault();
    remember(); commitBuffer();
  } else if (e.key === 'Escape' && buf.trim()) {
    e.preventDefault();
    remember(); commit(null, undefined, { literal: true });
  } else if (e.altKey && !e.ctrlKey && !e.metaKey && /^[1-5]$/.test(e.key) && cands[+e.key - 1]) {
    e.preventDefault();
    remember(); commit(cands[+e.key - 1].d);
  } else if (e.key === 'Backspace' && !buf) {
    const out = $('out');
    if (!out.value.trim()) return;
    e.preventDefault(); remember();
    // Reopen the selected word, or the word before the output cursor.
    const selected = out.selectionStart !== out.selectionEnd;
    const endAt = out.selectionEnd;
    const m = out.value.slice(0, endAt).match(/(\S+)(\s*)$/);
    if (!selected && !m) return;
    const start = selected ? out.selectionStart : m.index;
    const end = selected ? out.selectionEnd : start + m[1].length;
    const last = history[history.length - 1];
    const exact = !selected && endAt === out.value.length && last && out.value.endsWith(last.text);
    const word = out.value.slice(start, end);
    const roman = exact ? last.roman : /[a-zA-Z]/.test(word) ? word
      : word.replace(/[\u0900-\u097f\u200c\u200d]+/g, romanize);
    if (exact) history.pop(); else history.length = 0;
    out.setSelectionRange(start, end);
    out.scrollTop = out.scrollHeight;
    setHighlight(start, end);
    $('inp').value = roman || '';
    changed(); render();
  }
});

$('copy').addEventListener('click', async () => {
  if (composing || (!engine && $('inp').value.trim())) return;
  if ($('inp').value.trim()) remember();
  commitBuffer();
  const text = $('out').value;
  let ok = true;
  try { await navigator.clipboard.writeText(text); }
  catch {
    // Copy the same snapshot even if permission handling took time and the
    // user has continued editing. Never substitute the current output here.
    const focused = document.activeElement;
    const fallback = document.createElement('textarea');
    fallback.value = text;
    fallback.readOnly = true;
    fallback.tabIndex = -1;
    fallback.setAttribute('aria-hidden', 'true');
    fallback.style.cssText = 'position:fixed;left:0;top:0;opacity:0;pointer-events:none';
    $('type-tool').appendChild(fallback);
    try { fallback.select(); ok = document.execCommand('copy'); } catch { ok = false; }
    finally { fallback.remove(); focused?.focus({ preventScroll: true }); }
  }
  const t = $('toast');
  t.textContent = ok ? 'कपी भयो ✓ Copied' : 'कपी गर्न मिलेन — पाठ select गरेर कपी गर्नुहोस्';
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2200);
});

$('clear').addEventListener('click', () => {
  if (!$('out').value && !$('inp').value) return;
  remember();
  history.length = 0; $('out').value = ''; $('inp').value = ''; editable = false;
  setHighlight(null); syncEditable(); changed(); saveDraft(); render(); $('inp').focus();
});

// Compact only for a focused editor at normal zoom. Do not mistake pinch zoom
// for a keyboard, or scroll the user away from their work on every resize.
if (window.visualViewport) {
  const vv = window.visualViewport;
  const sync = () => {
    const active = document.activeElement;
    const inTool = $('type-tool').contains(active);
    const wasOpen = document.body.classList.contains('kbd');
    const open = inTool && vv.scale === 1 && vv.height < window.innerHeight * 0.8;
    document.body.classList.toggle('kbd', open);
    if (open && !wasOpen) $('type-tool').scrollIntoView({ block: 'start' });
  };
  vv.addEventListener('resize', sync);
  document.addEventListener('focusin', sync);
  document.addEventListener('focusout', () => setTimeout(sync, 0));
}

restoreDraft();
historyButtons();
render();
load();
if (matchMedia('(hover: hover)').matches) $('inp').focus();  // don't pop the keyboard on phones
