import assert from 'node:assert/strict';
import { test } from 'node:test';
import { METRES } from '../../assets/chhanda/metres.js';
import { scan, analyse, align, splitPadas, suggestWords, rebaseOverrides } from '../../assets/chhanda/engine.js';
import { changedRange, pendingWord, transliterateEdit } from '../../assets/chhanda/inline.js';

const bhujanga = METRES[0];
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
test('three formulae expand to their independently specified patterns', () => {
  assert.deepEqual(METRES.map(m => m.pattern), ['LGGLGGLGGLGG', 'GGLGLLLGLLGLGG', 'GGGLLGLGLLLGGGLGGLG']);
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
