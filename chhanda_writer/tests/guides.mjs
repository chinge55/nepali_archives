import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {scan} from '../../assets/chhanda/engine.js';

const {guides} = JSON.parse(readFileSync(new URL('../../assets/chhanda/guides.json', import.meta.url)));
const {metres} = JSON.parse(readFileSync(new URL('../../assets/chhanda/catalogue.json', import.meta.url)));

test('guide examples match the published fixed metre or its explicit final-weight allowance', () => {
  for (const metre of metres) {
    const patterns = metre.pattern ? [metre.pattern] : metre.patterns || [];
    if (!patterns.length) continue;
    for (const text of guides[metre.id].example.lines) {
      const reading = scan(text);
      assert.deepEqual(reading.issues, [], metre.id);
      const exact = patterns.includes(reading.pattern);
      const flexible = metre.kind === 'varnika' && patterns.some(p =>
        p.endsWith('G') && reading.pattern === p.slice(0, -1) + 'L');
      assert.ok(exact || flexible, metre.id + ': ' + text);
      if (!exact) assert.match(guides[metre.id].example.note, /अन्तिम लघु/, metre.id);
    }
  }
});

test('annotated groups reconstruct the original examples without changing any words', () => {
  for (const [id, guide] of Object.entries(guides)) {
    guide.example.lines.forEach((line, i) => assert.equal(guide.example.reading[i].join(''), line, id));
  }
});

test('alternating guides retain odd and even pada lengths and weight order', () => {
  const expected = {
    viyogini: ['LLGLLGLGLG', 'LLGGLLGLGLG'],
    pushpitagra: ['LLLLLLGLGLGG', 'LLLLGLLGLGLGG'],
  };
  for (const [id, patterns] of Object.entries(expected)) {
    guides[id].example.lines.forEach((text, i) => {
      const pattern = scan(text).pattern;
      assert.equal(pattern.slice(0, -1) + 'G', patterns[i], id);
    });
  }
  const readings = scan(guides.anushtup.example.lines[0]).pattern;
  assert.equal(readings.length, 16);
  assert.equal(readings.slice(4, 7), 'LGG');
  assert.equal(readings.slice(12, 15), 'LGL');
});

test('matra examples explain the final-short-as-long reading where needed', () => {
  const expected = {giti:[12,18], aupachchhandasika:[16,18], padakulak:[16]};
  for (const [id, counts] of Object.entries(expected)) {
    guides[id].example.lines.forEach((text, i) => {
      const pattern = scan(text).pattern;
      const actual = [...pattern].reduce((total, w) => total + (w === 'G' ? 2 : 1), 0);
      const finalAllowance = actual + 1 === counts[i] && pattern.endsWith('L');
      assert.ok(actual === counts[i] || finalAllowance, id);
      if (finalAllowance) assert.match(guides[id].example.note, /अन्तिम.*गुरु/, id);
    });
  }
  assert.deepEqual(guides.jhyaure.example.reading[0].map(chunk => scan(chunk).syllables.length), [5,5,6]);
});

test('yati examples divide at the stated syllable positions and complete words', () => {
  const divisions = {vasanta:[8,6], shardul:[12,7], malini:[8,7], shikharini:[6,11],
    shalini:[4,7], sragdhara:[7,7,7], mandakranta:[4,6,7], prithvi:[8,9],
    vamshastha:[5,7], mattamayuri:[4,9]};
  for (const [id, counts] of Object.entries(divisions)) {
    const chunks = guides[id].example.reading[0];
    assert.deepEqual(chunks.map(chunk => scan(chunk).syllables.length), counts, id);
    for (const chunk of chunks.slice(0,-1)) assert.match(chunk, /\s$/, id);
  }
});
