// Drafts and analysis stay in this browser. Only static assets are fetched.
const $ = id => document.getElementById(id);
const VERSION = new URL(import.meta.url).searchParams.get('v') || '';
const versioned = path => `${path}?v=${encodeURIComponent(VERSION)}`;
const DRAFT_KEY = 'nepaliarchives:chhanda:draft:v1';
const notice = message => { $('notice').textContent = message; };
const element = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};
let bootstrapAttempt = 0;
$('boot-retry').addEventListener('click', boot);

async function start() {
  const attempt = bootstrapAttempt++;
  const [{ METRES, VOCABULARY }, { analyse, rebaseOverrides, splitPadas, suggestWords, digits, weightName }, { pendingWord, changedRange, transliterateEdit }] = await Promise.all([
    import(`${versioned('./metres.js')}&attempt=${attempt}`), import(`${versioned('./engine.js')}&attempt=${attempt}`),
    import(`${versioned('./inline.js')}&attempt=${attempt}`),
  ]);
  const poem = $('poem');
  let state = { version: 2, text: poem.value, metre: METRES[0].id, overrides: {}, finalFlexible: true, mode: 'devanagari' };
  let parts = [], readings = [], active = 0, composing = false, timer, preview = null;
  let typingEngine = null, typingLoading = false, typingAttempt = 0, dirtyRoman = null;
  let vocabulary = [...VOCABULARY], undo = [], redo = [], suggestionTimer;
  let selection = { start: 0, end: 0 }, storageOK = true;
  const currentMetre = () => METRES.find(m => m.id === state.metre);
  const clone = value => JSON.parse(JSON.stringify(value));
  const snapshot = () => ({ ...clone(state), selection: { ...selection } });

  function validProject(value) {
    if (!value || ![1, 2].includes(value.version) || typeof value.text !== 'string' || value.text.length > 500000 ||
      !METRES.some(m => m.id === value.metre) || typeof value.finalFlexible !== 'boolean' ||
      value.pending !== undefined && typeof value.pending !== 'string') throw new Error('Invalid draft');
    const overrides = {};
    if (value.overrides && typeof value.overrides === 'object' && !Array.isArray(value.overrides)) {
      for (const [key, choice] of Object.entries(value.overrides)) {
        const colon = key.indexOf(':'), pos = Number(key.slice(0, colon)), word = key.slice(colon + 1);
        if (colon > 0 && Number.isInteger(pos) && pos >= 0 && word && value.text.slice(pos, pos + word.length) === word && choice === 'drop') overrides[key] = choice;
      }
    }
    const oldPending = value.version === 1 ? (value.pending || '').slice(0, 2000) : '';
    return { version: 2, text: value.text + (oldPending ? (value.text && !/\s$/.test(value.text) ? ' ' : '') + oldPending : ''),
      metre: value.metre, overrides, finalFlexible: value.finalFlexible,
      mode: value.mode === 'roman' || oldPending ? 'roman' : 'devanagari' };
  }

  function save() {
    try {
      if (state.text) localStorage.setItem(DRAFT_KEY, JSON.stringify(state));
      else localStorage.removeItem(DRAFT_KEY);
      storageOK = true;
      $('draft-status').textContent = state.text ? 'यस ब्राउजरमा सुरक्षित' : '';
    } catch {
      storageOK = false;
      $('draft-status').textContent = 'ब्राउजरमा सुरक्षित भएन। मस्यौदा फाइल डाउनलोड गर्नुहोस्।';
    }
  }

  // Preserve choices for unchanged words before/after an edit, rebasing offsets.
  function preserveReadings(oldText, text) {
    return rebaseOverrides(oldText, text, state.overrides);
  }

  function remember() {
    undo.push(snapshot()); if (undo.length > 100) undo.shift(); redo = [];
  }
  function action(fn) { remember(); fn(); sync(); render(); save(); }
  function sync() {
    if (poem.value !== state.text) poem.value = state.text;
    $('roman-mode').checked = state.mode === 'roman';
    $('metre-select').value = state.metre;
    $('final-flexible').checked = state.finalFlexible;
    $('undo').disabled = !undo.length; $('redo').disabled = !redo.length;
    if (typingEngine) renderRoman();
  }
  function travel(from, to) {
    if (!from.length) return;
    to.push(snapshot()); const previous = from.pop();
    state = validProject(previous); selection = previous.selection || { start: 0, end: 0 };
    dirtyRoman = null;
    sync(); poem.focus(); poem.setSelectionRange(selection.start, selection.end); render(); save();
  }
  function edited() {
    let updated = poem.value, caret = poem.selectionStart;
    if (state.mode === 'roman') {
      const area = changedRange(state.text, updated);
      if (typingEngine) {
        const converted = transliterateEdit(state.text, updated, caret, word => typingEngine.candidates(word, 1)[0]?.d || word);
        updated = converted.text; caret = converted.caret;
      } else dirtyRoman = { start: Math.min(dirtyRoman?.start ?? area.start, area.start),
        end: Math.max(area.end, (dirtyRoman?.end ?? area.end) + updated.length - state.text.length) };
    }
    state.overrides = preserveReadings(state.text, updated); state.text = updated;
    if (poem.value !== updated) { poem.value = updated; poem.setSelectionRange(caret, caret); }
    selection = { start: caret, end: poem.selectionEnd };
    clearTimeout(timer); timer = setTimeout(() => { render(); save(); }, 75);
    $('undo').disabled = !undo.length; $('redo').disabled = !redo.length;
  }
  function insert(text, startPos = selection.start, endPos = selection.end) {
    action(() => {
      const updated = state.text.slice(0, startPos) + text + state.text.slice(endPos);
      state.overrides = preserveReadings(state.text, updated); state.text = updated;
      selection = { start: startPos + text.length, end: startPos + text.length };
    });
    poem.focus(); poem.setSelectionRange(selection.start, selection.end);
  }
  function options(part) {
    const overrides = {};
    for (const [key, value] of Object.entries(state.overrides)) {
      const colon = key.indexOf(':'), pos = Number(key.slice(0, colon));
      if (pos >= part.start && pos < part.end) overrides[`${pos - part.start}:${key.slice(colon + 1)}`] = value;
    }
    return { overrides, finalFlexible: state.finalFlexible };
  }
  const statusLabels = { match: '✓ लय मिल्यो', partial: 'अधुरो पाउ', mismatch: '△ लय जाँच्नुहोस्', uncertain: '? पाठ जाँच्नुहोस्', empty: '', typing: 'लेख्दै…' };

  function render() {
    preview = null; $('word-preview').hidden = true;
    const metre = currentMetre();
    $('guide-heading').textContent = metre.name;
    $('metre-description').textContent = metre.description;
    $('metre-ganas').textContent = `गण: ${metre.ganas.join(' · ')}${metre.tail ? ' · ' + [...metre.tail].map(() => 'गुरु').join(' · ') : ''}`;
    $('pause-note').textContent = metre.pauseNote;
    $('metre-pattern').replaceChildren(...metre.ganas.map((g, i) => {
      const node = element('span');
      const group = metre.pattern.slice(i * 3, i * 3 + 3);
      node.append(element('b', [...group].map(w => w === 'G' ? 'ग' : 'ल').join(' ')));
      return node;
    }));
    if (metre.tail) $('metre-pattern').append(element('span', [...metre.tail].map(() => 'ग').join(' ')));
    $('example-text').textContent = metre.example;
    $('example-source').href = metre.source;
    $('example-source').textContent = `लक्ष्मीप्रसाद देवकोटा · ${metre.citation}`;
    $('example-page').textContent = `साहित्यरस संस्करण · PDF पृष्ठ ${digits(metre.page)} · मुद्रित पृष्ठ ${metre.folio}। मूल पृष्ठसँग तुलना गरिएको अंश।`;

    parts = splitPadas(state.text);
    active = parts.findIndex(p => selection.start >= p.start && selection.start <= p.end);
    if (active < 0) active = parts.findIndex(p => p.start > selection.start);
    if (active < 0) {
      if (!parts.length || /[\n/|]\s*$/.test(state.text.slice(parts.at(-1)?.end || 0))) {
        parts.push({ text: '', start: state.text.length, end: state.text.length, stanza: parts.at(-1)?.stanza || 0 });
      }
      active = parts.length - 1;
    }
    const pending = state.mode === 'roman' ? pendingWord(state.text, selection.start) : null;
    readings = parts.map(p => {
      const localStart = pending ? pending.start - p.start : -1;
      const waiting = localStart >= 0 && pending.end <= p.end;
      const text = waiting ? p.text.slice(0, localStart) + ' '.repeat(pending.end - pending.start) + p.text.slice(pending.end - p.start) : p.text;
      const reading = analyse(text, metre, options(p));
      return waiting ? { ...reading, status: 'typing' } : reading;
    });
    const part = parts[active], reading = readings[active];
    $('active-label').textContent = `पाउ ${digits(active + 1)}`;
    const tabs = parts.map((p, i) => {
      const button = element('button', `${digits(i + 1)} ${readings[i].status === 'match' ? '✓' : readings[i].status === 'mismatch' ? '△' : '◌'}`, 'ch-pada');
      button.type = 'button'; button.dataset.status = readings[i].status;
      button.setAttribute('aria-label', `पाउ ${digits(i + 1)}: ${statusLabels[readings[i].status]}`);
      button.setAttribute('aria-pressed', String(i === active));
      button.addEventListener('click', () => {
        selection = { start: p.start, end: p.start }; poem.focus(); poem.setSelectionRange(p.start, p.start); render();
      }); return button;
    });
    $('pada-tabs').replaceChildren(...tabs);
    $('analysis-status').textContent = statusLabels[reading.status] + (reading.flexible && reading.status === 'match' ? ' · पदान्त छुटसहित' : '');
    $('analysis-status').dataset.status = reading.status;
    $('editor-live-status').textContent = reading.status === 'empty' ? '' : `${statusLabels[reading.status]} · ${digits(reading.syllables.length)}/${digits(metre.pattern.length)}`;
    $('editor-live-status').dataset.status = reading.status;
    $('editor-live-pattern').textContent = reading.status === 'partial' ? `अझै ${digits(metre.pattern.length - reading.syllables.length)} अक्षर` : '';
    $('counts').textContent = `${digits(reading.syllables.length)} / ${digits(metre.pattern.length)} अक्षर · ${digits(reading.matras)} मात्रा`;
    const slots = reading.slots.map(slot => {
      const node = element(slot.syllable ? 'button' : 'div', undefined, `ch-slot ch-${slot.kind}${metre.pauses.includes(slot.position) ? ' ch-pause' : ''}`);
      node.append(element('small', slot.position ? digits(slot.position) : 'थप'),
        element('span', slot.syllable?.text || '·'),
        element('span', slot.syllable ? (slot.syllable.weight === 'G' ? 'ग' : 'ल') + (slot.kind === 'flexible' ? '*' : '') : '—'),
        element('span', slot.expected ? `चाहिने ${slot.expected === 'G' ? 'ग' : 'ल'}` : 'बढी', 'ch-expected'));
      if (slot.syllable) {
        node.type = 'button';
        const s = slot.syllable;
        const explanation = `“${s.text}”: ${weightName(s.weight)}। ${s.reasons.join(' ')}${slot.kind === 'mismatch' ? ` यहाँ ${weightName(slot.expected)} चाहिन्छ।` : ''}${slot.kind === 'flexible' ? ' पाउको अन्त्यमा गुरुको ठाउँमा लघु मानिएको छ।' : ''}`;
        node.setAttribute('aria-label', explanation);
        node.addEventListener('click', () => {
          $('syllable-detail').textContent = explanation;
          selection = { start: part.start + s.start, end: part.start + s.end };
          poem.focus({ preventScroll: true }); poem.setSelectionRange(selection.start, selection.end);
          // Selection is available for replacing the highlighted syllable/word.
          queueSuggestions();
        });
      }
      return node;
    });
    $('scansion').replaceChildren(...slots);
    $('syllable-detail').textContent = 'अक्षर थिचेर लघु वा गुरु हुनुको कारण हेर्नुहोस्। माथिल्लो पङ्क्तिमा तपाईंको पाठ, तल चाहिने तौल छ।';
    const missing = metre.pattern.length - reading.syllables.length;
    let hint = reading.status === 'partial' ? `अझै ${digits(missing)} अक्षर: ${[...reading.remaining].map(weightName).join(' · ')}`
      : reading.status === 'mismatch' ? missing > 0 ? `${digits(missing)} अक्षर कम छन्। सङ्केत गरिएका स्थानको तौल पनि जाँच्नुहोस्।`
        : missing < 0 ? `${digits(-missing)} अक्षर बढी छन्। सङ्केत गरिएका स्थान जाँच्नुहोस्।`
          : 'अक्षर सङ्ख्या पुगेको छ। सङ्केत गरिएका स्थानमा लघु–गुरुको क्रम वा शब्दको उच्चारण जाँच्नुहोस्।'
        : reading.status === 'uncertain' ? reading.oversized ? 'यो पाउ धेरै लामो छ। / वा नयाँ हरफले पाउ छुट्याउनुहोस्।' : reading.issues.join(' ')
          : reading.status === 'match' ? 'यो नतिजा देखाइएको काव्यपाठमा आधारित छ। शब्दको उच्चारण आफ्नो पाठसँग मिलाउनुहोस्।' : 'ल = लघु, ग = गुरु। एउटा हरफमा एउटा पाउ लेखेर सुरु गर्न सकिन्छ।';
    for (const pause of reading.pauses) if (pause.wordBoundary === false) hint += ` ${digits(pause.position)}औँ अक्षरमा शब्द सकिएको छैन; यतिको पाठ जाँच्नुहोस्।`;
    $('analysis-hint').textContent = hint;

    const choices = reading.words.filter(w => w.canDrop).map(w => {
      const label = element('label', w.text), select = element('select');
      select.setAttribute('aria-label', `${w.text} को अन्तिम अ`);
      for (const [value, text] of [['keep', 'अ उच्चारित'], ['drop', 'अ नबोल्ने']]) {
        const option = element('option', text); option.value = value; select.append(option);
      }
      select.value = w.dropped ? 'drop' : 'keep';
      select.addEventListener('change', () => action(() => {
        const key = `${part.start + w.start}:${w.text}`;
        if (select.value === 'drop') state.overrides[key] = 'drop'; else delete state.overrides[key];
      }));
      label.append(select); return label;
    });
    $('reading-choices').replaceChildren(...choices);
    $('reading-count').textContent = choices.length ? `(${digits(choices.length)})` : '';
    if (!choices.length) $('reading-choices').append(element('p', 'यो पाउमा अन्तिम अ बदल्न मिल्ने शब्द छैन।', 'ch-caption'));
    const nonempty = parts.filter(p => p.text.trim());
    const stanza = new Map();
    nonempty.forEach(p => stanza.set(p.stanza, (stanza.get(p.stanza) || 0) + 1));
    const complete = [...stanza.values()].filter(count => count === 4).length;
    const matches = readings.filter(r => r.status === 'match').length;
    $('stanza-summary').textContent = nonempty.length ? `${digits(nonempty.length)} पाउमध्ये ${digits(matches)} मा तौल मिल्यो। ${digits(complete)} श्लोकमा चार पाउ छन्।` : '';
    sync(); queueSuggestions();
  }

  function insertionContext() {
    const part = parts[active];
    return { part, start: Math.max(0, Math.min(part.text.length, selection.start - part.start)),
      end: Math.max(0, Math.min(part.text.length, selection.end - part.start)) };
  }
  function queueSuggestions() {
    clearTimeout(suggestionTimer);
    if ($('word-panel').open) suggestionTimer = setTimeout(renderSuggestions, 100);
  }
  function renderSuggestions() {
    const { part, start: begin, end } = insertionContext();
    if (!part) return;
    const prefix = $('word-prefix').value.trim();
    const response = suggestWords(part.text, begin, end, currentMetre(), vocabulary, prefix, options(part));
    $('suggestion-context').textContent = begin !== end ? 'छानिएको पाठको ठाउँमा मिल्ने शब्दहरू।'
      : `कर्सर भएको ठाउँमा मिल्ने शब्दहरू${readings[active].remaining ? ` · बाँकी ${[...readings[active].remaining].map(w => w === 'G' ? 'ग' : 'ल').join(' ')}` : ''}।`;
    const buttons = response.results.map(candidate => {
      const button = element('button', candidate.word); button.type = 'button';
      button.addEventListener('click', () => {
        preview = { ...candidate, start: part.start + begin, end: part.start + end };
        $('preview-line').textContent = candidate.candidate;
        $('word-preview').hidden = false;
        $('insert-word').focus({ preventScroll: true });
      }); return button;
    });
    $('word-choices').replaceChildren(...buttons);
    if (!buttons.length) $('word-choices').append(element('p', response.needsRepair ? 'पहिले पाउको सुरुतिरको तौल मिलाउनुहोस् वा बदल्ने शब्द छान्नुहोस्।'
      : readings[active].status === 'match' && begin === end ? 'पाउको तौल पुगेको छ। अर्को पाउ सुरु गर्न सक्नुहुन्छ।'
        : 'यो ढाँचामा मिल्ने शब्द भेटिएन। सुरुको अक्षर बदल्नुहोस् वा अर्को शब्द छान्नुहोस्।', 'ch-caption'));
  }

  METRES.forEach(metre => {
    const option = element('option', metre.name); option.value = metre.id; $('metre-select').append(option);
  });
  $('metre-select').addEventListener('change', () => action(() => { state.metre = $('metre-select').value; }));
  poem.addEventListener('beforeinput', event => {
    if (event.inputType === 'historyUndo' || event.inputType === 'historyRedo') {
      event.preventDefault(); event.inputType === 'historyUndo' ? travel(undo, redo) : travel(redo, undo);
    } else if (!composing && !event.isComposing) remember();
  });
  poem.addEventListener('compositionstart', () => { remember(); composing = true; });
  poem.addEventListener('compositionend', () => { composing = false; edited(); });
  poem.addEventListener('input', event => { if (!composing && !event.isComposing) edited(); });
  function selectionChanged() {
    selection = { start: poem.selectionStart, end: poem.selectionEnd };
    const current = parts[active];
    if (!current || selection.start < current.start || selection.start > current.end) render();
    else queueSuggestions();
    renderRoman();
  }
  poem.addEventListener('click', selectionChanged); poem.addEventListener('keyup', selectionChanged);
  poem.addEventListener('select', selectionChanged);
  poem.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
      event.preventDefault(); event.shiftKey ? travel(redo, undo) : travel(undo, redo);
    } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'y') {
      event.preventDefault(); travel(redo, undo);
    }
  });
  $('undo').addEventListener('click', () => travel(undo, redo)); $('redo').addEventListener('click', () => travel(redo, undo));
  $('final-flexible').addEventListener('change', () => action(() => { state.finalFlexible = $('final-flexible').checked; }));
  $('word-prefix').addEventListener('input', queueSuggestions);
  $('word-panel').addEventListener('toggle', queueSuggestions);
  $('insert-word').addEventListener('click', () => { if (preview) { const choice = preview; insert(choice.inserted, choice.start, choice.end); } });
  $('cancel-preview').addEventListener('click', () => { preview = null; $('word-preview').hidden = true; });
  $('example-open').addEventListener('click', () => $('example-dialog').showModal());
  $('example-close').addEventListener('click', () => $('example-dialog').close());
  $('use-example').addEventListener('click', () => {
    action(() => { state.text = currentMetre().example; state.overrides = {}; selection = { start: 0, end: 0 }; });
    $('example-dialog').close();
    poem.focus(); poem.setSelectionRange(0, 0); poem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  });
  $('clear').addEventListener('click', () => {
    action(() => { state.text = ''; state.overrides = {}; selection = { start: 0, end: 0 }; dirtyRoman = null; });
    document.querySelector('.ch-file-menu').open = false;
    notice('नयाँ कविता सुरु गर्नुहोस्। फर्काउने बटनले अघिल्लो पाठ फर्काउँछ।'); poem.focus();
  });
  $('copy').addEventListener('click', async () => {
    finishRoman();
    const captured = state.text;
    try { await navigator.clipboard.writeText(captured); notice('पाठ कपी भयो।'); }
    catch {
      const copyBox = element('textarea'); copyBox.value = captured; document.body.append(copyBox); copyBox.select();
      const copied = document.execCommand('copy'); copyBox.remove();
      notice(copied ? 'पाठ कपी भयो।' : 'पाठ छानेर Ctrl/⌘+C प्रयोग गर्नुहोस्।');
    }
  });
  function download(content, name, type) {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const anchor = element('a'); anchor.href = url; anchor.download = name; document.body.append(anchor); anchor.click(); anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  $('download-text').addEventListener('click', () => { finishRoman(); download(state.text, 'kabita.txt', 'text/plain;charset=utf-8'); });
  $('export-project').addEventListener('click', () => download(JSON.stringify(state, null, 2) + '\n', 'chhanda-draft.json', 'application/json'));
  $('import-project').addEventListener('change', async event => {
    const file = event.target.files[0]; if (!file) return;
    try {
      if (file.size > 2000000) throw new Error('Large file');
      const imported = validProject(JSON.parse(await file.text()));
      action(() => { state = imported; selection = { start: 0, end: 0 }; });
      document.querySelector('.ch-file-menu').open = false;
      if (state.mode === 'roman') loadTyping();
      notice('मस्यौदा खुल्यो। फर्काउने बटनले अघिल्लो पाठ फर्काउँछ।');
    } catch { notice('मस्यौदा खुलेन। यस साधनबाट सुरक्षित गरिएको JSON फाइल छान्नुहोस्। तपाईंको पाठ उस्तै छ।'); }
    event.target.value = '';
  });

  async function fetchJSON(path) {
    const response = await fetch(versioned(path)); if (!response.ok) throw new Error('Asset unavailable'); return response.json();
  }
  let lexicon;
  // The same static core is shared with /type/. No draft text is sent with it.
  fetchJSON('../type/lexicon-core.json').then(data => {
    lexicon = data;
    vocabulary = [...new Set([...VOCABULARY, ...data.words.map(row => row[0])])];
    typingEngine?.setLexicon(data); queueSuggestions(); renderRoman();
  }).catch(() => { /* The bundled common vocabulary remains available. */ });

  async function loadTyping() {
    if (typingLoading || typingEngine) return;
    typingLoading = true; $('roman-retry').hidden = true;
    $('roman-status').textContent = 'टाइप गर्ने साधन तयार हुँदैछ…';
    try {
      const [{ createEngine }, rules, autocorrect] = await Promise.all([
        import(`${versioned('../type/engine.js')}&attempt=${typingAttempt++}`),
        fetchJSON('../type/rules.json'), fetchJSON('../type/autocorrect.json').catch(() => ({})),
      ]);
      typingEngine = createEngine(rules, autocorrect); typingEngine.setEnglishFirst(false);
      $('chhanda-tool').dataset.typingReady = 'true';
      if (lexicon) typingEngine.setLexicon(lexicon);
      $('roman-status').textContent = '';
      if (dirtyRoman && state.mode === 'roman') {
        const converted = transliterateEdit('', state.text, selection.start, word => typingEngine.candidates(word, 1)[0]?.d || word, { range: dirtyRoman });
        state.overrides = preserveReadings(state.text, converted.text); state.text = converted.text;
        selection = { start: converted.caret, end: converted.caret }; dirtyRoman = null;
        sync(); poem.setSelectionRange(selection.start, selection.end); render(); save();
      }
      renderRoman();
    } catch {
      $('roman-status').textContent = 'रोमन साधन खुलेन। नेपालीमा सिधै लेख्न सकिन्छ।'; $('roman-retry').hidden = false;
    } finally { typingLoading = false; }
  }
  function currentRoman() { return state.mode === 'roman' ? pendingWord(state.text, selection.start) : null; }
  function romanCandidates() { const word = currentRoman(); return typingEngine && word ? typingEngine.candidates(word.text, 5) : []; }
  function commitRoman(word) {
    const pending = currentRoman();
    if (!word || !pending) return;
    insert(word, pending.start, pending.end);
    renderRoman();
  }
  function finishRoman() {
    if (composing || state.mode !== 'roman' || !typingEngine) return;
    const pending = currentRoman();
    if (!pending) return;
    const converted = transliterateEdit(state.text, state.text, selection.start, word => typingEngine.candidates(word, 1)[0]?.d || word,
      { force: true, range: { start: pending.start, end: pending.end } });
    if (converted.text !== state.text) action(() => {
      state.overrides = preserveReadings(state.text, converted.text); state.text = converted.text;
      selection = { start: converted.caret, end: converted.caret };
    });
  }
  function renderRoman() {
    const candidates = romanCandidates();
    $('roman-choices').hidden = !candidates.length;
    $('roman-choices').replaceChildren(...candidates.map(candidate => {
      const button = element('button', candidate.d); button.type = 'button';
      button.addEventListener('click', () => commitRoman(candidate.d)); return button;
    }));
  }
  $('roman-mode').addEventListener('change', () => {
    const roman = $('roman-mode').checked;
    if (!roman) finishRoman();
    action(() => { state.mode = roman ? 'roman' : 'devanagari'; if (!roman) dirtyRoman = null; });
    if (roman) loadTyping();
    else { $('roman-status').textContent = ''; $('roman-retry').hidden = true; }
    renderRoman(); poem.focus(); poem.setSelectionRange(selection.start, selection.end);
  });
  $('roman-retry').addEventListener('click', loadTyping);

  try {
    const stored = localStorage.getItem(DRAFT_KEY);
    if (stored && !state.text) { state = validProject(JSON.parse(stored)); notice('अघिल्लो स्थानीय मस्यौदा फर्काइएको छ।'); }
  } catch { notice('अघिल्लो मस्यौदा खुल्न सकेन। लेख्न सकिन्छ; सुरक्षित मस्यौदा फाइल भए खोल्नुहोस्।'); }
  window.addEventListener('pagehide', () => { if (composing) edited(); save(); });
  document.addEventListener('visibilitychange', () => { if (document.hidden) { if (composing) edited(); save(); } });
  function keyboardLayout() {
    const editing = document.activeElement?.id === 'poem';
    document.body.classList.toggle('ch-keyboard', editing && innerWidth < 760 && (window.visualViewport?.height || innerHeight) < 520);
  }
  window.visualViewport?.addEventListener('resize', keyboardLayout);
  document.addEventListener('focusin', keyboardLayout);
  document.addEventListener('focusout', () => setTimeout(keyboardLayout, 0));
  sync(); render();
  if (state.mode === 'roman') loadTyping();
  $('boot-status').hidden = true;
  $('chhanda-tool').dataset.ready = 'true';
  if (!storageOK) notice('मस्यौदा फाइलमा डाउनलोड गरेर सुरक्षित राख्नुहोस्।');
}

function boot() {
  $('boot-retry').hidden = true;
  start().catch(() => {
    $('boot-status').textContent = 'लेखन सहायक खुलेन। लेखेको पाठ यहीँ छ; फेरि प्रयास गर्नुहोस्।';
    $('boot-retry').hidden = false;
  });
}
boot();
