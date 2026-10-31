import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {createMetres} from '../../assets/chhanda/metres.js';
import {analyse, metrePatterns, suggestWords} from '../../assets/chhanda/engine.js';
import {problemRanges} from '../../assets/chhanda/underlines.js';

const {metres: entries} = JSON.parse(readFileSync(new URL('../../assets/chhanda/catalogue.json', import.meta.url)));
const {guides} = JSON.parse(readFileSync(new URL('../../assets/chhanda/guides.json', import.meta.url)));
const all = createMetres([...entries, {id:'muktachhanda',kind:'free-verse',name:'मुक्तछन्द',writer:'muktachhanda'}]
  .map(entry => ({...entry, groups:guides[entry.id].groups, tips:guides[entry.id].reading,
    example:guides[entry.id].example.lines.join('\n')})));
const metre = id => all.find(m => m.id === id);

test('all 31 named metres and free verse have an available writing mode', () => {
  assert.equal(all.length, 32);
  assert.equal(new Set(all.map(m => m.id)).size, 32);
  for (const entry of all) {
    assert.equal(entry.writer, entry.id);
    assert.ok(['pattern','count','guided'].includes(entry.mode));
  }
});

test('source-preserving examples work in every fixed and alternating mode', () => {
  for (const entry of all.filter(m => m.mode === 'pattern')) {
    entry.example.split('\n').forEach((text, pada) => assert.equal(analyse(text,entry,{pada}).status,'match',entry.id));
  }
});

test('both Upajati families accept either component without forcing a pronunciation', () => {
  for (const [id, lines] of [['upajati',['कतै खरानी छरि भुस्‌ कतै ता,','सुत्न्या दिनैदिन्‌ इलमै बिगारी,']],
    ['upajati_12',['गरीब भन्छौ? सुखको म झैं धनी','मिल्दैन संसारभरी कतै पनि।']]]) {
    const results = lines.map(line => analyse(line,metre(id)));
    assert.ok(results.every(r => r.status === 'match'));
    assert.notEqual(results[0].targetPattern[0],results[1].targetPattern[0]);
    assert.equal(analyse(lines[0].replace('गरीब','गरिब'),metre(id),{finalFlexible:false}).words.some(w => w.dropped),false);
  }
});

test('alternating patterns follow the pada position, including repeated pairs', () => {
  for (const id of ['viyogini','pushpitagra']) {
    const [odd,even] = guides[id].example.lines;
    for (const pada of [0,2,4]) assert.equal(analyse(odd,metre(id),{pada}).status,'match');
    for (const pada of [1,3,5]) assert.equal(analyse(even,metre(id),{pada}).status,'match');
    assert.equal(analyse(even,metre(id),{pada:0}).status,'mismatch');
  }
});

test('bahr endings keep their own rules even with the classical final-flexible option on', () => {
  for (const entry of all.filter(m => m.kind === 'bahr')) {
    assert.equal(entry.allowFinalFlexible,false);
    const patterns = metrePatterns(entry);
    assert.equal(patterns.length,entry.id === 'hazaj_musamman_salim' ? 1 : 2);
    assert.ok(patterns[0].endsWith('G'));
  }
  const entry = metre('hazaj_musaddas_mahzuf');
  assert.equal(analyse('बिना मन्‌को भई यो ज्यू जिएकि',entry).status,'mismatch');
  assert.equal(analyse(entry.example + ' क',entry).status,'match');
});

test('matra modes count alternating targets and explicitly retain raw final-short weights', () => {
  for (const [id, expected] of [['giti',[12,18]],['aupachchhandasika',[16,18]],['padakulak',[16]]]) {
    guides[id].example.lines.forEach((text,pada) => {
      const result = analyse(text,metre(id),{pada});
      assert.equal(result.status,'counted',id);
      assert.equal(result.targetCount,expected[pada]);
      assert.equal(result.measure,'matras');
      assert.equal(result.matras + Number(result.flexible),expected[pada]);
    });
  }
  const [_,even] = guides.giti.example.lines;
  const literal = analyse(even,metre('giti'),{pada:1,finalFlexible:false});
  assert.equal(literal.status,'partial');
  assert.equal(literal.matras,17);
});

test('count assistance never declares complete metre correctness', () => {
  const text = guides.anushtup.example.reading[0][0];
  const result = analyse(text,metre('anushtup'));
  assert.equal(result.status,'counted');
  assert.equal(result.targetCount,8);
  assert.deepEqual(problemRanges(text,[{start:0,end:text.length}],[result]),[]);
});

test('folk and free-verse writing have neutral counts and no false error underlines', () => {
  const text = 'मेरो आफ्नै लयको कविता';
  for (const id of ['jhyaure','muktachhanda']) {
    const result = analyse(text,metre(id));
    assert.equal(result.status,'guided');
    assert.equal(result.targetCount,null);
    assert.deepEqual(problemRanges(text,[{start:0,end:text.length}],[result]),[]);
    const response = suggestWords('',0,0,metre(id),['मन','वन'],'म');
    assert.deepEqual(response.results.map(row => row.word),['मन']);
  }
});

test('count overflow, unknown input and oversized lines remain distinct', () => {
  assert.equal(analyse('क '.repeat(9),metre('anushtup')).status,'mismatch');
  assert.equal(analyse('क abc',metre('padakulak')).status,'uncertain');
  for (const id of ['muktachhanda','giti']) {
    const result=analyse('क '.repeat(121),metre(id));
    assert.equal(result.status,'uncertain');
    assert.equal(result.slots.length,0);
  }
});

test('suggestions can start either permitted Upajati component', () => {
  const words=['कतै','सुत्न्या'];
  const response=suggestWords('',0,0,metre('upajati'),words);
  assert.deepEqual(response.results.map(r=>r.word),words);
});
