// Independent, deterministic spelling-based scansion. See chhanda_writer/rules.md.
const CON = /[क-हळऴक़-य़]/u;
const VOWELS = new Set(Array.from('अआइईउऊऋॠऌॡएऐओऔऍऎऑऒ'));
const MARKS = new Set(Array.from('ािीुूृॄॢॣेैोौॅॆॉॊ'));
const LONG = new Set(Array.from('आईऊॠॡएऐओऔाीूॄॣेैोौ'));
const MOD = new Set(Array.from('ंँः'));
const JOIN = new Set(['\u200c', '\u200d']);
const WORD = /[अ-हळऴक़-ॣािीुूृॄॅॆेैॉॊोौ्ँंः़\u200c\u200d]+/gu;
const punctuation = /^[\s,;:!?\-–—…।॥|/“”‘’"'()[\]{}]*$/u;
export const weightName = w => w === 'G' ? 'गुरु' : 'लघु';
export const digits = n => String(n).replace(/\d/g, c => '०१२३४५६७८९'[Number(c)]);

export function rebaseOverrides(oldText, text, overrides = {}) {
  let head = 0, tail = 0;
  while (head < oldText.length && head < text.length && oldText[head] === text[head]) head++;
  while (tail < oldText.length - head && tail < text.length - head && oldText.at(-tail - 1) === text.at(-tail - 1)) tail++;
  const result = {};
  const wordChar = /[\p{L}\p{M}\p{N}\u200c\u200d]/u;
  for (const [key, value] of Object.entries(overrides)) {
    const colon = key.indexOf(':'), pos = Number(key.slice(0, colon)), word = key.slice(colon + 1);
    const intact = at => at >= 0 && text.slice(at, at + word.length) === word &&
      !wordChar.test(text[at - 1] || '') && !wordChar.test(text[at + word.length] || '');
    if (pos + word.length <= head && intact(pos)) result[key] = value;
    else if (pos + word.length > oldText.length - tail) {
      const shifted = pos + text.length - oldText.length;
      if (intact(shifted)) result[`${shifted}:${word}`] = value;
    }
  }
  return result;
}

function parseWord(text, start, dropFinal) {
  const syllables = [], issues = [];
  let i = 0;
  while (i < text.length) {
    const begin = i;
    let onset = 0, implicit = false, vowel;
    if (CON.test(text[i])) {
      while (i < text.length && CON.test(text[i])) {
        onset++; i++;
        if (text[i] === '़') i++;
        if (text[i] !== '्') break;
        i++;
        while (JOIN.has(text[i])) i++;
        if (!CON.test(text[i] || '')) {
          if (syllables.length) {
            const last = syllables.at(-1);
            last.end = start + i;
            last.weight = 'G'; last.reasons.push('हलन्त व्यञ्जनले अक्षर बन्द गरेको छ।');
          } else issues.push('स्वरविनाको व्यञ्जनलाई अघिल्लो अक्षरसँग जोडेर जाँच्नुहोस्।');
          onset = 0; break;
        }
      }
      if (!onset) continue;
      if (MARKS.has(text[i])) vowel = text[i++];
      else { vowel = 'अ'; implicit = true; }
    } else if (VOWELS.has(text[i])) vowel = text[i++];
    else {
      if (!JOIN.has(text[i])) issues.push(`“${text[i]}” को स्वर वा जोडाइ स्पष्ट छैन।`);
      i++; continue;
    }
    let closed = false;
    while (MOD.has(text[i]) || JOIN.has(text[i])) {
      if ('ंः'.includes(text[i])) closed = true;
      i++;
    }
    const heavy = LONG.has(vowel) || closed;
    syllables.push({ start: start + begin, end: start + i, onset, implicit,
      weight: heavy ? 'G' : 'L',
      reasons: [closed ? 'अनुस्वार वा विसर्गका कारण गुरु।' : LONG.has(vowel) ? 'दीर्घ स्वर भएकाले गुरु।' : 'ह्रस्व स्वर भएकाले लघु।'] });
  }
  const last = syllables.at(-1);
  const canDrop = syllables.length > 1 && last?.implicit && last.end === start + text.length;
  if (canDrop && dropFinal) {
    const removed = syllables.pop(), prev = syllables.at(-1);
    prev.end = removed.end; prev.weight = 'G';
    prev.reasons.push('तपाईंले अन्तिम अ नबोल्ने पाठ रोज्नुभएको छ; अन्तिम व्यञ्जनले अक्षर बन्द गर्छ।');
  }
  return { text, start, end: start + text.length, syllables, issues, canDrop, dropped: canDrop && !!dropFinal };
}

export function scan(text, overrides = {}) {
  const words = [], issues = [];
  let end = 0;
  for (const m of text.matchAll(WORD)) {
    if (!punctuation.test(text.slice(end, m.index))) issues.push('नेपालीबाहेकका अक्षर वा अङ्कको छन्द जाँच गरिएको छैन।');
    const key = `${m.index}:${m[0]}`;
    const word = parseWord(m[0], m.index, overrides[key] === 'drop');
    words.push({ ...word, key }); issues.push(...word.issues);
    end = m.index + m[0].length;
  }
  if (!punctuation.test(text.slice(end))) issues.push('नेपालीबाहेकका अक्षर वा अङ्कको छन्द जाँच गरिएको छैन।');
  const syllables = words.flatMap(w => w.syllables.map(s => ({ ...s, reasons: [...s.reasons], word: w.text })));
  for (let i = 0; i < syllables.length; i++) {
    const s = syllables[i], next = syllables[i + 1];
    if (next?.onset >= 2 && /^\s*$/.test(text.slice(s.end, next.start))) {
      if (s.weight === 'L') {
        s.weight = 'G'; s.reasons.push('पछाडि संयुक्त व्यञ्जन आएकाले गुरु।');
      }
    }
    s.text = text.slice(s.start, s.end);
  }
  return { words, syllables, issues: [...new Set(issues)], pattern: syllables.map(s => s.weight).join('') };
}

// Edit-distance alignment keeps a missing syllable from shifting all later feedback.
export function align(syllables, pattern, finalFlexible = true) {
  const n = syllables.length, m = pattern.length;
  const dp = Array.from({ length: n + 1 }, () => Array(m + 1).fill(Infinity));
  const prev = Array.from({ length: n + 1 }, () => Array(m + 1));
  dp[0][0] = 0;
  for (let i = 0; i <= n; i++) for (let j = 0; j <= m; j++) {
    const put = (a, b, cost, kind) => {
      if (cost < dp[a][b]) { dp[a][b] = cost; prev[a][b] = { i, j, kind }; }
    };
    if (i < n && j < m) {
      const flexible = finalFlexible && i === n - 1 && j === m - 1 && syllables[i].weight === 'L' && pattern[j] === 'G';
      put(i + 1, j + 1, dp[i][j] + (syllables[i].weight === pattern[j] || flexible ? 0 : 1.1), flexible ? 'flexible' : syllables[i].weight === pattern[j] ? 'match' : 'mismatch');
    }
    if (i < n) put(i + 1, j, dp[i][j] + 1, 'extra');
    if (j < m) put(i, j + 1, dp[i][j] + 1, 'missing');
  }
  const slots = [];
  let i = n, j = m;
  while (i || j) {
    const p = prev[i][j];
    slots.push({ kind: p.kind, syllable: i > p.i ? syllables[i - 1] : null,
      expected: j > p.j ? pattern[j - 1] : null, position: j > p.j ? j : null });
    i = p.i; j = p.j;
  }
  return { slots: slots.reverse(), distance: dp[n][m] };
}

export function metrePatterns(metre, pada = 0) {
  const patterns = metre.sequence ? [metre.sequence[pada % metre.sequence.length]]
    : metre.patterns || (metre.pattern ? [metre.pattern] : []);
  return metre.extraFinalShort ? [...patterns, ...patterns.map(pattern => pattern + 'L')] : patterns;
}

function countReading(result, metre, options) {
  const n = result.syllables.length, oversized = n > 120;
  const measure = metre.measure || 'syllables';
  const actual = measure === 'matras' ? result.syllables.reduce((sum, s) => sum + (s.weight === 'G' ? 2 : 1), 0) : n;
  const target = metre.targets?.[(options.pada || 0) % metre.targets.length] || null;
  const flexible = measure === 'matras' && target === actual + 1 && result.pattern.endsWith('L')
    && options.finalFlexible !== false && metre.allowFinalFlexible !== false;
  const counted = actual + Number(flexible);
  let used = 0;
  const slots = oversized ? [] : result.syllables.map((syllable, i) => {
    used += measure === 'matras' ? syllable.weight === 'G' ? 2 : 1 : 1;
    return {syllable, position:i + 1, expected:null, kind:target && used > target ? 'extra' : 'match'};
  });
  return { ...result, slots, pauses:[], flexible, oversized, remaining:'', targetPattern:'',
    targetCount:target, measure, matras:result.syllables.reduce((sum, s) => sum + (s.weight === 'G' ? 2 : 1), 0),
    status: result.issues.length || oversized ? 'uncertain' : !n ? 'empty' : !target ? 'guided'
      : counted === target ? 'counted' : counted < target ? 'partial' : 'mismatch' };
}

export function analyse(text, metre, options = {}) {
  const { overrides = {}, pada = 0 } = options;
  const finalFlexible = options.finalFlexible !== false && metre.allowFinalFlexible !== false;
  const patterns = metrePatterns(metre, pada);
  if (!patterns.length) return countReading(scan(text, overrides), metre, options);
  // Select a permitted reading without changing either the text or pronunciation.
  const scanned = scan(text, overrides);
  let selected = patterns[0], best = Infinity;
  if (scanned.syllables.length <= 120) for (const candidate of patterns) {
    const score = candidate.startsWith(scanned.pattern) ? 0 : align(scanned.syllables, candidate, finalFlexible).distance;
    if (score < best) {best = score; selected = candidate;}
  }
  const pattern = selected;
  const result = scanned, n = result.syllables.length;
  const prefixFits = n < pattern.length && result.pattern === pattern.slice(0, n);
  // Bound pathological paste costs without truncating or altering the user's draft.
  const oversized = n > 120;
  const alignment = oversized ? { slots: [], distance: n } : prefixFits ? {
    slots: [...pattern].map((expected, i) => ({ expected, position: i + 1, syllable: result.syllables[i] || null, kind: i < n ? 'match' : 'missing' })),
    distance: pattern.length - n,
  } : align(result.syllables, pattern, finalFlexible);
  const status = result.issues.length || oversized ? 'uncertain' : !n ? 'empty'
    : n === pattern.length && alignment.distance === 0 ? 'match' : prefixFits ? 'partial' : 'mismatch';
  const pauses = (metre.pauses || []).map(position => {
    const s = result.syllables[position - 1], next = result.syllables[position];
    return { position, wordBoundary: !s || !next ? null : /[\s,;:!?।॥]/.test(text.slice(s.end, next.start)) };
  });
  return { ...result, ...alignment, status, remaining: prefixFits || !n ? pattern.slice(n) : '', pauses,
    matras: result.syllables.reduce((sum, s) => sum + (s.weight === 'G' ? 2 : 1), 0),
    flexible: alignment.slots.some(s => s.kind === 'flexible'), oversized,
    targetPattern:pattern, targetCount:pattern.length, measure:'syllables' };
}

export function splitPadas(text) {
  const parts = [];
  const re = /[^\n\r/|।॥]+/g;
  for (const m of text.matchAll(re)) {
    if (!m[0].trim()) continue;
    const previous = parts.at(-1);
    const gap = previous ? text.slice(previous.end, m.index) : '';
    const stanza = previous ? previous.stanza + (/\n\s*\n/.test(gap) ? 1 : 0) : 0;
    parts.push({ text: m[0], start: m.index, end: m.index + m[0].length, stanza });
  }
  return parts;
}

export function suggestWords(text, start, end, metre, words, prefix = '', options = {}) {
  const before = text.slice(0, start), after = text.slice(end);
  const lead = before && !/[\s/|।॥]$/.test(before) ? ' ' : '';
  const tail = after && !/^[\s,;!?/|।॥]/.test(after) ? ' ' : '';
  const original = analyse(text, metre, options), results = [];
  const patterns = metrePatterns(metre, options.pada || 0);
  for (const word of words) {
    if (prefix && !word.startsWith(prefix)) continue;
    const inserted = lead + word + tail;
    const candidate = before + inserted + after;
    const scanned = scan(candidate, rebaseOverrides(text, candidate, options.overrides));
    const n = scanned.pattern.length;
    const flexible = options.finalFlexible !== false && metre.allowFinalFlexible !== false;
    const fullPattern = patterns.find(p => scanned.pattern === p || flexible && n === p.length &&
      scanned.pattern === p.slice(0, -1) + 'L' && p.endsWith('G'));
    const partialPattern = patterns.find(p => n < p.length && p.startsWith(scanned.pattern));
    const counted = !patterns.length ? countReading(scanned, metre, options) : null;
    const full = !!fullPattern || counted && ['counted', 'guided'].includes(counted.status);
    const partial = !!partialPattern || counted?.status === 'partial';
    if (scanned.issues.length || !full && !partial) continue;
    if (start !== end && candidate === text) continue;
    results.push({ word, inserted, candidate, status: counted?.status || (full ? 'match' : 'partial'), remaining: (fullPattern || partialPattern || '').slice(n) });
    if (results.length === 8) break;
  }
  return { results, needsRepair: !['empty', 'partial', 'match', 'counted', 'guided'].includes(original.status) };
}
