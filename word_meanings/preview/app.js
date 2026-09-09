(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const card = $('#meaningCard'), collection = $('#collection'), article = $('#textColumn');
  const action = $('#selectionLookup'), input = $('#lookupInput');
  const mobile = matchMedia('(max-width: 700px)');
  const storageKey = 'nepali-word-collection';
  let work = null, current = null, selection = null, loading = false;
  const make = (tag, text, cls) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  };
  const button = (text, onClick, cls) => {
    const node = make('button', text, cls);
    node.type = 'button'; node.onclick = onClick; return node;
  };
  const known = word => !!work && Object.hasOwn(work.words, word);
  const normalize = word => word.normalize('NFC').trim().replace(/[\u200c\u200d]+$/u, '');
  const number = n => String(n).replace(/[0-9]/g, digit => '०१२३४५६७८९'[Number(digit)]);

  function saved() {
    try {
      const value = JSON.parse(localStorage.getItem(storageKey) || '[]');
      return Array.isArray(value) ? [...new Set(value.filter(w => typeof w === 'string' && known(w)))] : [];
    } catch { return []; }
  }
  function store(items, status) {
    try { localStorage.setItem(storageKey, JSON.stringify(items)); return true; }
    catch { status.textContent = 'यस ब्राउजरमा सङ्ग्रह राख्न सकिएन।'; return false; }
  }
  function statusNode() {
    const node = make('p', '', 'storage-status'); node.setAttribute('role', 'status'); return node;
  }
  function hideSelectionAction() { action.classList.remove('visible'); action.disabled = true; }
  function syncModal() {
    const collectionOpen = !collection.hidden;
    const meaningModal = !!current && mobile.matches;
    card.setAttribute('aria-modal', String(meaningModal));
    $('#meaningScrim').hidden = !meaningModal;
    $('#scrim').hidden = !collectionOpen;
    for (const node of [$('.topbar'), $('.reader-intro'), article]) node.inert = collectionOpen || meaningModal;
    card.inert = collectionOpen;
  }
  function emptyCard() {
    card.replaceChildren(make('p', 'पाठमा एउटा शब्द छान्नुहोस्। अर्थ यहाँ खुल्छ।', 'empty-state'));
  }
  function closeMeaning(restore = true) {
    const trigger = current?.trigger;
    current = null; card.classList.remove('open'); emptyCard(); syncModal();
    if (restore && trigger?.isConnected) trigger.focus({preventScroll: true});
  }
  function senseGroup(group, filter = () => true) {
    const section = make('section', undefined, 'sense-group');
    section.append(make('p', [group.grammar, group.etymology].filter(Boolean).join(' · '), 'sense-head'));
    const list = make('ul', undefined, 'sense-list');
    (group.senses || []).forEach((sense, index) => {
      if (!filter(index) || !sense.text) return;
      const item = make('li', sense.text);
      for (const example of sense.examples || []) {
        const text = typeof example === 'string' ? example : example.value || example.text;
        if (text) item.append(make('p', text, 'example'));
      }
      list.append(item);
    });
    section.append(list); return section;
  }
  function renderMeaning() {
    const {word, line, entryIndex} = current;
    card.replaceChildren();
    const close = button('×', () => closeMeaning(), 'card-close');
    close.id = 'closeMeaning'; close.setAttribute('aria-label', 'अर्थ बन्द गर्नुहोस्');
    card.append(close, make('div', 'शब्दार्थ', 'card-label'), make('h2', word));
    const quote = line ? make('blockquote', line, 'context-quote') : null;
    if (!known(word)) {
      card.append(make('p', 'यस शब्दको अर्थ अहिले उपलब्ध छैन।', 'unavailable'),
        make('p', 'शब्दकोशमा नभेटिँदैमा मूल लेखाइ गलत हुँदैन।', 'muted'));
      if (quote) card.append(quote);
    } else {
      const data = work.words[word], entry = data.entries[entryIndex];
      if (data.kind !== 'exact') card.append(make('p', `${word} → ${entry.headword} · शब्दकोशको सम्बन्धित रूप`, 'association-note'));
      const source = make('p', `${entry.label} · ${entry.language === 'ne' ? 'नेपाली' : 'English'} `, 'grammar');
      if (/^https?:\/\//.test(entry.sourceUrl || '')) {
        const link = make('a', 'स्रोत'); link.href = entry.sourceUrl; link.target = '_blank'; link.rel = 'noopener noreferrer'; source.append(link);
      }
      const context = line && work.contextSenses.find(c => c.word === word && c.line === line &&
        c.source === entry.source && c.entryId === entry.id);
      if (context) {
        const group = entry.groups[context.groupIndex];
        card.append(make('div', 'यस प्रसङ्गमा', 'context-label'),
          senseGroup(group, i => i === context.senseIndex));
        if (quote) card.append(quote);
        const other = make('details', undefined, 'other-senses');
        other.append(make('summary', 'अरू शब्दकोश अर्थहरू'));
        entry.groups.forEach((g, i) => other.append(senseGroup(g, j => i !== context.groupIndex || j !== context.senseIndex)));
        card.append(other);
      } else {
        card.append(make('div', 'शब्दकोश अर्थहरू', 'context-label'));
        let shown = 0;
        entry.groups.forEach(group => {
          const start = shown;
          const visible = group.senses.map((sense, index) => ({sense, index}))
            .filter(item => item.sense.text).slice(0, Math.max(0, 2 - shown));
          shown += visible.length;
          if (shown > start) card.append(senseGroup(group, i => visible.some(item => item.index === i)));
        });
        if (quote) card.append(quote);
        const total = entry.groups.reduce((count, group) => count + group.senses.filter(sense => sense.text).length, 0);
        if (total > shown) {
          const more = make('details', undefined, 'other-senses');
          more.append(make('summary', `थप शब्दकोश अर्थहरू (${number(total - shown)})`));
          let skipped = 0;
          entry.groups.forEach(group => {
            const indexes = group.senses.map((sense, index) => ({sense, index})).filter(item => item.sense.text);
            const rest = indexes.filter(() => skipped++ >= shown);
            if (rest.length) more.append(senseGroup(group, i => rest.some(item => item.index === i)));
          });
          card.append(more);
        }
      }
      const tabs = make('div', undefined, 'source-tabs'); tabs.setAttribute('aria-label', 'शब्दकोशका प्रविष्टिहरू');
      data.entries.forEach((e, i) => {
        const tab = button(`${e.headword} · ${e.label}`, () => { current.entryIndex = i; renderMeaning(); }, 'source-tab');
        tab.setAttribute('aria-pressed', String(i === entryIndex)); tabs.append(tab);
      });
      card.append(source);
      if (data.entries.length > 1) {
        const sources = make('details', undefined, 'source-options');
        sources.append(make('summary', 'अरू स्रोत र प्रविष्टिहरू'), tabs); card.append(sources);
      }
      const isSaved = saved().includes(word), feedback = statusNode();
      const save = button(isSaved ? '✓ सङ्ग्रहमा छ · हटाउनुहोस्' : '＋ मेरो सङ्ग्रहमा राख्नुहोस्', () => {
        const old = saved(), next = old.includes(word) ? old.filter(w => w !== word) : [...old, word];
        if (store(next, feedback)) {
          renderCollection(); feedback.textContent = '';
          const kept = next.includes(word);
          save.textContent = kept ? '✓ सङ्ग्रहमा छ · हटाउनुहोस्' : '＋ मेरो सङ्ग्रहमा राख्नुहोस्';
          save.classList.toggle('saved', kept); save.setAttribute('aria-pressed', String(kept));
        }
      }, 'save-button');
      save.id = 'saveWord'; save.setAttribute('aria-pressed', String(isSaved)); save.classList.toggle('saved', isSaved); card.append(save, feedback);
    }
    card.classList.add('open'); hideSelectionAction(); syncModal(); card.scrollTop = 0;
    close.focus({preventScroll: true});
  }
  function lookup(value, trigger = input, line = '') {
    const word = normalize(value);
    if (!word || /\s/u.test(word)) { $('#lookupStatus').textContent = 'एउटा शब्द मात्र लेख्नुहोस्।'; return; }
    if (!work) { $('#lookupStatus').textContent = 'शब्दकोश लोड भएपछि फेरि प्रयास गर्नुहोस्।'; return; }
    $('#lookupStatus').textContent = '';
    current = {word, trigger, line, entryIndex: 0}; renderMeaning();
  }
  function renderCollection() {
    const items = saved(), box = $('#savedWords');
    $('#collectionCount').textContent = number(items.length); box.replaceChildren();
    if (!items.length) box.append(make('p', 'अहिलेसम्म कुनै शब्द राखिएको छैन।', 'muted'));
    for (const word of items) {
      const row = make('div', undefined, 'saved-item');
      const open = button(word, () => { closeCollection(false); lookup(word, $('#collectionToggle')); });
      const remove = button('हटाउनुहोस्', () => {
        if (store(saved().filter(w => w !== word), $('#collectionStatus'))) {
          renderCollection(); if (current?.word === word) renderMeaning();
          $('#closeCollection').focus({preventScroll: true});
        }
      });
      remove.setAttribute('aria-label', `${word} हटाउनुहोस्`); row.append(open, remove); box.append(row);
    }
  }
  function closeCollection(restore = true) {
    collection.hidden = true; $('#collectionToggle').setAttribute('aria-expanded', 'false'); syncModal();
    if (restore) $('#collectionToggle').focus({preventScroll: true});
  }
  function updateSelection() {
    if ((current && mobile.matches) || !collection.hidden) { hideSelectionAction(); return; }
    const s = getSelection();
    if (!s?.rangeCount || s.isCollapsed || !article.contains(s.anchorNode) || !article.contains(s.focusNode)) {
      selection = null; hideSelectionAction(); return;
    }
    const range = s.getRangeAt(0), word = normalize(s.toString());
    if (!word || /\s/u.test(word) || range.startContainer !== range.endContainer || range.startContainer.nodeType !== Node.TEXT_NODE) {
      selection = null; hideSelectionAction(); return;
    }
    const text = range.startContainer.textContent;
    const start = text.lastIndexOf('\n', range.startOffset - 1) + 1;
    let end = text.indexOf('\n', range.endOffset); if (end < 0) end = text.length;
    selection = {word, line: text.slice(start, end)};
    action.textContent = `${word} · अर्थ`; action.disabled = false; action.classList.add('visible');
  }
  async function load() {
    if (loading) return; loading = true;
    $('#loadingState').hidden = false; $('#loadError').hidden = true;
    try {
      const response = await fetch('work.json'); if (!response.ok) throw Error('unavailable');
      const data = await response.json();
      if (typeof data.text !== 'string' || !data.words || !Array.isArray(data.contextSenses)) throw Error('invalid data');
      work = data; $('#title').textContent = data.title;
      $('#sourceLine').textContent = `${data.title} · ${data.author} · मूल पाठ`;
      article.replaceChildren(make('div', data.text, 'original-text')); renderCollection();
    } catch {
      $('#loadError').hidden = false;
      if (!work) {
        // The complete static HTML text remains readable without dictionary data.
        $('#sourceLine').textContent = 'मुनामदन · लक्ष्मीप्रसाद देवकोटा';
      }
    } finally { loading = false; $('#loadingState').hidden = true; }
  }

  article.tabIndex = -1;
  collection.setAttribute('role', 'dialog'); collection.setAttribute('aria-modal', 'true');
  const collectionStatus = statusNode(); collectionStatus.id = 'collectionStatus'; collection.append(collectionStatus);
  document.addEventListener('selectionchange', updateSelection);
  action.onpointerdown = event => event.preventDefault();
  action.onclick = () => { if (selection) lookup(selection.word, article, selection.line); };
  $('#lookupForm').onsubmit = event => { event.preventDefault(); lookup(input.value); };
  $('#retryLoad').onclick = load;
  $('#collectionToggle').onclick = () => {
    closeMeaning(false); hideSelectionAction(); collection.hidden = false;
    $('#collectionToggle').setAttribute('aria-expanded', 'true'); renderCollection(); syncModal();
    $('#closeCollection').focus({preventScroll: true});
  };
  $('#closeCollection').onclick = () => closeCollection();
  $('#scrim').onclick = () => closeCollection(); $('#meaningScrim').onclick = () => closeMeaning();
  $('#clearCollection').onclick = () => {
    if (store([], collectionStatus)) { renderCollection(); collectionStatus.textContent = ''; }
  };
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      if (!collection.hidden) { event.preventDefault(); closeCollection(); }
      else if (current) { event.preventDefault(); closeMeaning(); }
    }
    const modal = !collection.hidden ? collection : current && mobile.matches ? card : null;
    if (event.key === 'Tab' && modal) {
      const controls = [...modal.querySelectorAll('button,a[href],input,summary,[tabindex="0"]')]
        .filter(node => !node.disabled && node.getClientRects().length > 0);
      const index = controls.indexOf(document.activeElement);
      if (event.shiftKey && index <= 0) { event.preventDefault(); controls.at(-1)?.focus({preventScroll: true}); }
      else if (!event.shiftKey && (index < 0 || index === controls.length - 1)) { event.preventDefault(); controls[0]?.focus({preventScroll: true}); }
    }
  });
  mobile.addEventListener('change', syncModal);
  window.addEventListener('storage', () => { renderCollection(); if (current) renderMeaning(); });
  emptyCard(); renderCollection(); load();
})();
