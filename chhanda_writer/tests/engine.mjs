import assert from 'node:assert/strict';
import { test } from 'node:test';
import { METRES } from '../../assets/chhanda/metres.js';
import { scan, analyse, align, splitPadas, suggestWords, rebaseOverrides } from '../../assets/chhanda/engine.js';
import { changedRange, pendingWord, transliterateEdit, inputScript } from '../../assets/chhanda/inline.js';
import { problemRanges } from '../../assets/chhanda/underlines.js';
import { readFileSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { assessmentIsCurrent, matchesCataloguePattern } from '../pipeline/review-state.mjs';

const bhujanga = METRES[0];
test('archive metre definitions agree with every supported writer pattern', () => {
  const catalogue = JSON.parse(readFileSync(new URL('../../assets/chhanda/catalogue.json', import.meta.url))).metres;
  for (const metre of METRES) {
    const entry = catalogue.find(m => m.id === metre.id);
    assert.equal(entry.name, metre.name);
    assert.equal(entry.pattern, metre.pattern);
    assert.equal(entry.writer, metre.id);
  }
  assert.equal(catalogue.find(m => m.id === 'prithvi').pattern, 'LGLLLGLGLLLGLGGLG');
  assert.equal(catalogue.find(m => m.id === 'swagata').pattern, 'GLGLLLGLLGG');
});
test('upajati recognises both component readings without changing writer templates', () => {
  const catalogue = JSON.parse(readFileSync(new URL('../../assets/chhanda/catalogue.json', import.meta.url))).metres;
  const entry = catalogue.find(m => m.id === 'upajati');
  // Two source-preserved padas from Bhanubhakta's कतै खरानी छरि भुस्‌ कतै ता.
  const readings = ['सुत्न्या दिनैदिन्‌ इलमै बिगारी,', 'कतै खरानी छरि भुस्‌ कतै ता,'].map(text => scan(text).pattern);
  assert.deepEqual(readings, entry.patterns);
  assert.equal(METRES.some(m => m.id === 'upajati'), false);
});
test('the located Manoladdu ending follows anushtup without a universal fixed template', () => {
  const catalogue = JSON.parse(readFileSync(new URL('../../assets/chhanda/catalogue.json', import.meta.url))).metres;
  const entry = catalogue.find(m => m.id === 'anushtup');
  assert.equal(entry.pattern, undefined);
  assert.equal(entry.patterns, undefined);
  assert.equal(entry.writer, undefined);
  const padas = ['सानू यौटा मनोलड्डु', 'लेखनाथ अनाथको', 'लिनुहोला कृपासाथ', 'गहना पारि हातको'];
  padas.forEach((text, i) => {
    const reading = scan(text);
    assert.deepEqual(reading.issues, []);
    assert.equal(reading.syllables.length, 8);
    assert.equal(reading.pattern.slice(4, 7), i % 2 ? 'LGL' : 'LGG');
  });
});
test('Panchachamara has eight light-heavy pairs in source-preserved Dagbatti padas', () => {
  const catalogue = JSON.parse(readFileSync(new URL('../../assets/chhanda/catalogue.json', import.meta.url))).metres;
  const entry = catalogue.find(m => m.id === 'panchachamara');
  assert.equal(entry.pattern, 'LG'.repeat(8));
  for (const text of ['म सात वर्षको थिएँ, अबोध बालकै थिएँ,', 'कुनै कुरा थिएन थाह, मस्त नींदमा थिएँ,']) {
    assert.equal(scan(text).pattern, entry.pattern);
  }
  assert.equal(entry.writer, undefined);
});
test('twelve-syllable Upajati keeps Vamshastha and Indravamsha distinct from eleven-syllable Upajati', () => {
  const catalogue = JSON.parse(readFileSync(new URL('../../assets/chhanda/catalogue.json', import.meta.url))).metres;
  const entry = catalogue.find(m => m.id === 'upajati_12');
  assert.deepEqual(entry.patterns, ['LGLGGLLGLGLG', 'GGLGGLLGLGLG']);
  const padas = ['गरीब भन्छौ? सुखको म झैं धनी', 'मिल्दैन संसारभरी कतै पनि।'];
  padas.forEach((text, i) => {
    const reading = scan(text);
    assert.equal(reading.syllables.length, 12);
    assert.equal(align(reading.syllables, entry.patterns[i], true).distance, 0);
  });
  assert.ok(catalogue.find(m => m.id === 'upajati').patterns.every(p => p.length === 11));
  assert.equal(entry.writer, undefined);
});
test('the located Viyogini ending alternates ten and eleven syllables', () => {
  const catalogue = JSON.parse(readFileSync(new URL('../../assets/chhanda/catalogue.json', import.meta.url))).metres;
  const entry = catalogue.find(m => m.id === 'viyogini');
  const padas = ['उपकार गरुन् भनेर यो', 'प्रभुले मानिस देह बक्सियो', 'उपकार पटी तयार भै,', 'निज कर्तव्य समालिहाल है'];
  padas.forEach((text, i) => assert.equal(scan(text).pattern, i % 2 ? 'LLGGLLGLGLG' : 'LLGLLGLGLG'));
  // Alternating lengths cannot be represented as interchangeable fixed templates.
  assert.equal(entry.pattern, undefined);
  assert.equal(entry.patterns, undefined);
  assert.equal(entry.writer, undefined);
});
test('five archive bahr readings follow their reference feet in preserved Nepali lines', () => {
  const catalogue = JSON.parse(readFileSync(new URL('../../assets/chhanda/catalogue.json', import.meta.url))).metres;
  const examples = [
    ['ramal_musamman_mahzuf', 'GLGG'.repeat(3) + 'GLG', 'क्या सफाई हाइ हाई बम्बईका मालिनी'],
    ['hazaj_musamman_salim', 'LGGG'.repeat(4), 'भला सद्धै नआये आउ एकैपल्ट घर्‌सम्मन्,'],
    ['hazaj_musaddas_mahzuf', 'LGGG'.repeat(2) + 'LGG', 'बिना मन्‌को भई यो ज्यू जिएको,'],
    ['mutaqarib_musamman_mahzuf', 'LGG'.repeat(3) + 'LG', 'हरे ! मैसितै लाग खानू कती,'],
    ['kamil_musamman_salim', 'LLGLG'.repeat(4), 'दिनको पचास त के हजार पटक् कती समझाउनू,'],
  ];
  for (const [id, formula, text] of examples) {
    const entry = catalogue.find(m => m.id === id);
    assert.equal(entry.pattern, formula);
    assert.equal(scan(text).pattern, formula, id);
    assert.equal(entry.writer, undefined);
    assert.equal(matchesCataloguePattern(formula.slice(0, -1) + 'L', formula, entry), false);
    assert.equal(matchesCataloguePattern(formula + 'L', formula, entry), id !== 'hazaj_musamman_salim');
  }
  assert.equal(matchesCataloguePattern('LGGLGGLGGLGL', 'LGGLGGLGGLGG', { kind: 'varnika' }), true);
});
test('alternating and mora-based archive forms retain their stanza order and final-weight licence', () => {
  const catalogue = JSON.parse(readFileSync(new URL('../../assets/chhanda/catalogue.json', import.meta.url))).metres;
  for (const id of ['giti', 'pushpitagra', 'aupachchhandasika', 'padakulak']) {
    const entry = catalogue.find(m => m.id === id);
    assert.equal(entry.pattern, undefined);
    assert.equal(entry.patterns, undefined);
    assert.equal(entry.writer, undefined);
  }
  const heavyEnd = text => { const p = scan(text).pattern; return p.slice(0, -1) + 'G'; };
  assert.equal(heavyEnd('अब मति सब यो वितृष्ण गर्छु'), 'LLLLLLGLGLGG');
  assert.equal(heavyEnd('विभु भगवान्‌ यदुनाथमा म धर्छु'), 'LLLLGLLGLGLGG');
  const mora = text => [...scan(text).pattern].reduce((sum, w) => sum + (w === 'G' ? 2 : 1), 0);
  assert.deepEqual(['प्रतिभा मुटु हो मनुष्यताको', 'प्रतिभाले पद लिन्छ देवताको'].map(mora), [16, 18]);
  assert.deepEqual(['जय गणनायक ! मेरो', 'हृदय-कमलमा सदा गरी वास'].map(mora), [12, 17]);
  // The second Giti pada takes the documented final-short-as-long licence: 17 + 1.
  assert.equal(scan('हृदय-कमलमा सदा गरी वास').pattern.at(-1), 'L');
  assert.equal(catalogue.find(m => m.id === 'pramanika').pattern, 'LG'.repeat(4));
  assert.equal(scan('नटिप्नु हेर कोपिला').pattern, 'LG'.repeat(4));
});
test('an uncertain assessment leaves classification pending and reopens on text or source changes', () => {
  const work = mkdtempSync(path.join(tmpdir(), 'prosody-review-'));
  try {
    writeFileSync(path.join(work, 'source.html'), 'preserved source');
    const sha = crypto.createHash('sha256').update('preserved source').digest('hex');
    const metadata = { source: { html: 'source.html' }, prosody: {
      status: 'uncertain', text_sha256: 'text-digest', reviewed: '2026-10-31',
      evidence: [{ file: 'source.html', sha256: sha, locator: 'poem', note: 'Rhythm unresolved.' }],
    } };
    assert.equal(assessmentIsCurrent(work, metadata, 'text-digest'), true);
    assert.equal(metadata.prosody.status, 'uncertain');
    assert.equal(assessmentIsCurrent(work, metadata, 'changed-text'), false);
    writeFileSync(path.join(work, 'source.html'), 'changed source');
    assert.equal(assessmentIsCurrent(work, metadata, 'text-digest'), false);
  } finally { rmSync(work, { recursive: true }); }
});
test('a documented source gap is assessed until a preserved source becomes available', () => {
  const work = mkdtempSync(path.join(tmpdir(), 'prosody-gap-'));
  try {
    const metadata = { source: { html: 'missing.html' }, prosody: {
      status: 'uncertain', text_sha256: 'text-digest', reviewed: '2026-10-31', evidence: [],
      review_note: 'No preserved source is available to confirm the reading.',
    } };
    assert.equal(assessmentIsCurrent(work, metadata, 'text-digest'), true);
    metadata.prosody.review_note = '';
    assert.equal(assessmentIsCurrent(work, metadata, 'text-digest'), false);
    metadata.prosody.review_note = 'Source unavailable.';
    writeFileSync(path.join(work, 'missing.html'), 'new source');
    assert.equal(assessmentIsCurrent(work, metadata, 'text-digest'), false);
    metadata.prosody.status = 'reviewed';
    assert.equal(assessmentIsCurrent(work, metadata, 'text-digest'), false);
  } finally { rmSync(work, { recursive: true }); }
});
test('input script follows newly entered letters and ignores digits or punctuation', () => {
  assert.equal(inputScript('mero'), 'roman');
  assert.equal(inputScript('कविता'), 'devanagari');
  assert.equal(inputScript('मेरो naam '), 'roman');
  assert.equal(inputScript('mero नाम'), 'devanagari');
  assert.equal(inputScript('२०८३ 2026 ।!?'), null);
  assert.equal(inputScript('्ाँ\u200d'), null);
});
test('underlines identify the wrong syllable without marking a valid line', () => {
  const good = splitPadas(bhujanga.example)[0].text;
  const bad = good.replace('नटी', 'नाटी');
  const errors = text => { const parts = splitPadas(text); return problemRanges(text, parts, parts.map(p => analyse(p.text, bhujanga))); };
  assert.deepEqual(errors(good), []);
  assert.deepEqual(errors(bad), [{ start: 0, end: 2 }]);
  assert.equal(bad.slice(errors(bad)[0].start, errors(bad)[0].end), 'ना');
});
test('underlines wait for a boundary before flagging an otherwise valid unfinished line', () => {
  const parts = splitPadas('नटी');
  const reading = analyse(parts[0].text, bhujanga);
  assert.deepEqual(problemRanges('नटी', parts, [reading]), []);
  assert.deepEqual(problemRanges('नटी\n', parts, [reading]), [{ start: 1, end: 3 }]);
  assert.deepEqual(problemRanges('नटी।', parts, [reading]), [{ start: 1, end: 3 }]);
});
test('underline ranges retain whole-draft offsets and ignore pending or uncertain readings', () => {
  const bad = splitPadas(bhujanga.example)[0].text.replace('नटी', 'नाटी');
  const text = 'नटी\n' + bad, parts = splitPadas(text);
  const readings = parts.map(p => analyse(p.text, bhujanga));
  assert.deepEqual(problemRanges(text, parts, readings), [{ start: 1, end: 3 }, { start: 4, end: 6 }]);
  readings[1].status = 'typing';
  assert.deepEqual(problemRanges(text, parts, readings), [{ start: 1, end: 3 }]);
  readings[0].status = 'uncertain';
  assert.deepEqual(problemRanges(text, parts, readings), []);
});
const convert = word => ({ mero: 'मेरो', naam: 'नाम', kabita: 'कविता', ho: 'हो' }[word] || word);
test('inline Roman conversion commits words at boundaries in the same editor', () => {
  assert.deepEqual(transliterateEdit('mer', 'mero', 4, convert), { text: 'mero', caret: 4 });
  assert.deepEqual(transliterateEdit('mero', 'mero ', 5, convert), { text: 'मेरो ', caret: 5 });
  assert.deepEqual(transliterateEdit('', 'mero naam ho\n', 13, convert), { text: 'मेरो नाम हो\n', caret: 12 });
  assert.equal(transliterateEdit('मेरो ', 'मेरो naam.', 10, convert).text, 'मेरो नाम।');
});
test('inline conversion preserves existing text, selected replacements and structured tokens', () => {
  assert.equal(transliterateEdit('hello मेरो ', 'hello मेरो naam ', 16, convert).text, 'hello मेरो नाम ');
  assert.equal(transliterateEdit('मेरो नाम छ', 'मेरो kabita छ', 11, convert).text, 'मेरो kabita छ');
  assert.equal(transliterateEdit('मेरो नाम छ', 'मेरो k छ', 6, () => 'के').text, 'मेरो k छ');
  assert.equal(transliterateEdit('मेरो kabita छ', 'मेरो kabita  छ', 12, convert).text, 'मेरो कविता  छ');
  for (const text of ['test@example.org ', 'https://example.org ', 'covid19 ']) assert.equal(transliterateEdit('', text, text.length, convert).text, text);
  assert.equal(transliterateEdit('mero', 'mero', 4, convert, { force: true }).text, 'मेरो');
});
test('inline pending-word ranges remain separate from source text and preserve offsets', () => {
  assert.deepEqual(pendingWord('मेरो naam', 9), { start: 5, end: 9, text: 'naam' });
  assert.equal(pendingWord('test@example.org', 4), null);
  assert.deepEqual(changedRange('abc नाम', 'abc मेरो नाम'), { start: 4, end: 9, oldEnd: 4 });
});
test('the metre catalogue matches independently specified formulae and pause positions', () => {
  assert.equal(new Set(METRES.map(m => m.id)).size, METRES.length);
  assert.deepEqual(Object.fromEntries(METRES.map(m => [m.id, [m.pattern, m.pauses]])), {
    bhujanga: ['LGGLGGLGGLGG', []],
    vasanta: ['GGLGLLLGLLGLGG', [8]],
    shardul: ['GGGLLGLGLLLGGGLGGLG', [12]],
    malini: ['LLLLLLGGGLGGLGG', [8]],
    shikharini: ['LGGGGGLLLLLGGLLLG', [6]],
    totaka: ['LLGLLGLLGLLG', []],
    drutavilambita: ['LLLGLLGLLGLG', [4]],
    shalini: ['GGGGGLGGLGG', [4]],
    sragdhara: ['GGGGLGGLLLLLLGGLGGLGG', [7, 14]],
    mandakranta: ['GGGGLLLLLGGLGGLGG', [4, 10]],
  });
});
for (const [word, pattern] of Object.entries({
  'कवि': 'LL', 'कविता': 'LLG', 'माला': 'GG', 'कर्म': 'GL', 'भक्त': 'GL', 'राम्': 'G',
  'हँस': 'LL', 'हंस': 'GL', 'दुःख': 'GL', 'शक्ति': 'GL', 'प्रेम': 'GL',
  'अगाडि': 'LGL', 'छम्छमाउन्': 'GLGG', 'दीर्घकाल': 'GLGL', 'क्\u200dषमा': 'LG',
  'क़लम': 'LLL', 'ऋतु': 'LL', 'एउटा': 'GLG', 'कॄ': 'G',
})) test(`syllables and weights for ${word}`, () => {
  const result = scan(word);
  assert.equal(result.pattern, pattern);
  assert.deepEqual(result.issues, []);
  assert.equal(result.syllables.map(s => s.text).join(''), word);
});
test('a cluster across a word boundary closes the preceding short syllable', () => {
  assert.equal(scan('न प्रेम').pattern, 'GGL');
  assert.equal(scan('न, प्रेम').pattern, 'LGL');
});
test('final inherent vowel is kept until the writer explicitly selects another reading', () => {
  assert.equal(scan('मन').pattern, 'LL');
  const alternate = scan('मन', { '0:मन': 'drop' });
  assert.equal(alternate.pattern, 'G');
  assert.equal(alternate.syllables[0].text, 'मन');
  assert.equal(alternate.words[0].dropped, true);
  assert.equal(scan('न', { '0:न': 'drop' }).pattern, 'L');
});
for (const metre of METRES) test(`source-checked excerpts fit ${metre.name}`, () => {
  for (const part of splitPadas(metre.example)) assert.equal(analyse(part.text, metre).status, 'match', part.text);
});
test('pada-final flexibility is explicit and can be disabled', () => {
  const text = splitPadas(bhujanga.example)[0].text;
  assert.equal(analyse(text, bhujanga).flexible, true);
  assert.equal(analyse(text, bhujanga, { finalFlexible: false }).status, 'mismatch');
});
test('partial, empty, incompatible, unsupported, and oversized text stay distinct', () => {
  assert.equal(analyse('', bhujanga).status, 'empty');
  assert.equal(analyse('नटी', bhujanga).status, 'partial');
  assert.equal(analyse('माला', bhujanga).status, 'mismatch');
  assert.equal(analyse('नटी abc', bhujanga).status, 'uncertain');
  assert.equal(analyse('नटी १२', bhujanga).status, 'uncertain');
  assert.equal(analyse('न ्', bhujanga).status, 'uncertain');
  assert.equal(analyse('न '.repeat(121), bhujanga).oversized, true);
});
test('a correct unfinished prefix stays anchored to the beginning of the template', () => {
  const result = analyse('नटी', bhujanga);
  assert.deepEqual(result.slots.filter(s => s.syllable).map(s => s.position), [1, 2]);
  assert.ok(result.slots.slice(2).every(s => s.kind === 'missing'));
});
test('alignment isolates a missing or extra syllable instead of shifting subsequent weights', () => {
  const weights = pattern => [...pattern].map(weight => ({ weight }));
  const missing = align(weights('GGLLGLGLLLGGGLGGLG'), METRES[2].pattern, false);
  assert.equal(missing.slots.filter(s => s.kind === 'missing').length, 1);
  assert.equal(missing.slots.filter(s => s.kind === 'mismatch').length, 0);
  const extra = align(weights('LGGLGGLGGLGGG'), bhujanga.pattern, false);
  assert.equal(extra.slots.filter(s => s.kind === 'extra').length, 1);
});
test('explicit pada boundaries retain offsets and blank lines group stanzas', () => {
  const text = 'नटी / मेनका ।\nकटी ॥ भारी\n\nमसीनो';
  const parts = splitPadas(text);
  assert.equal(parts.length, 5);
  assert.deepEqual(parts.map(p => p.stanza), [0, 0, 0, 0, 1]);
  parts.forEach(p => assert.equal(text.slice(p.start, p.end), p.text));
});
test('reading choices follow unchanged words but are invalidated when the word changes', () => {
  assert.deepEqual(rebaseOverrides('मन वन', 'मेरा मन वन', { '0:मन': 'drop', '3:वन': 'drop' }), { '5:मन': 'drop', '8:वन': 'drop' });
  assert.deepEqual(rebaseOverrides('मन वन', 'मनको वन', { '0:मन': 'drop', '3:वन': 'drop' }), { '5:वन': 'drop' });
  assert.deepEqual(rebaseOverrides('मन', 'कमन', { '0:मन': 'drop' }), {});
});
test('suggestions recheck full context, respect prefix and never change the original', () => {
  const suggestions = suggestWords('नटी ', 4, 4, bhujanga, ['माला', 'मेनका', 'मन'], 'मे');
  assert.deepEqual(suggestions.results.map(r => r.word), ['मेनका']);
  assert.equal(suggestions.results[0].candidate, 'नटी मेनका');
  const replacement = suggestWords('नटी माला', 4, 8, bhujanga, ['मेनका']);
  assert.equal(replacement.results[0].candidate, 'नटी मेनका');
  assert.equal(suggestWords('न ', 2, 2, bhujanga, ['प्रेम']).results.length, 0);
});
