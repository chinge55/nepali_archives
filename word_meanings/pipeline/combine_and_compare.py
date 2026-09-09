#!/usr/bin/env python3
"""Local dictionary union and transparent surface-word coverage audit (stdlib only)."""
from pathlib import Path
from collections import Counter, defaultdict
from html.parser import HTMLParser
import csv, gzip, hashlib, html, json, re, sqlite3, unicodedata

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
OUT = ROOT / 'data/combined'
OUT.mkdir(parents=True, exist_ok=True)

def norm(s):
    return ' '.join(unicodedata.normalize('NFC', s).split())

def relaxed(s):
    return norm(s).replace('\u200c', '').replace('\u200d', '')

class Plain(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)
    def handle_starttag(self, tag, attrs):
        if tag in ('br', 'p', 'div', 'li'):
            self.parts.append(' ')
    def handle_endtag(self, tag):
        if tag in ('p', 'div', 'li'):
            self.parts.append(' ')

def plain(s):
    p = Plain(); p.feed(s); p.close()
    return ' '.join(''.join(p.parts).split())

def dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))

manifest = json.loads((ROOT/'sources.json').read_text())
for source in manifest:
    path = ROOT/'data/raw'/source['file']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source['sha256']

# Rebuild derived artifacts only; downloaded snapshots remain immutable.
dbpath = OUT/'dictionary.sqlite3'
if dbpath.exists():
    dbpath.unlink()
c = sqlite3.connect(dbpath)
c.executescript('''
CREATE TABLE sources(id TEXT PRIMARY KEY, metadata_json TEXT NOT NULL);
CREATE TABLE entries(id INTEGER PRIMARY KEY, source TEXT NOT NULL REFERENCES sources(id),
 source_record_id TEXT NOT NULL, headword TEXT NOT NULL, lookup_key TEXT NOT NULL,
 relaxed_key TEXT NOT NULL, definition_language TEXT NOT NULL, definitions_json TEXT NOT NULL,
 source_record_json TEXT NOT NULL, has_definition INTEGER NOT NULL,
 UNIQUE(source, source_record_id));
CREATE INDEX lookup_idx ON entries(lookup_key);
CREATE INDEX relaxed_idx ON entries(relaxed_key);
''')
for s in manifest:
    c.execute('INSERT INTO sources VALUES (?,?)', (s['id'], dump(s)))
counts = Counter(); keys = defaultdict(set); allkeys = defaultdict(set)

def add(source, sid, word, lang, definitions, original):
    key = norm(word)
    assert key, (source, sid)
    has_definition = any(any(s.get('text', '').strip() for s in group['senses']) for group in definitions)
    c.execute('INSERT INTO entries(source,source_record_id,headword,lookup_key,relaxed_key,definition_language,definitions_json,source_record_json,has_definition) VALUES (?,?,?,?,?,?,?,?,?)',
              (source, str(sid), word, key, relaxed(key), lang, dump(definitions), dump(original), int(has_definition)))
    counts[source] += 1; allkeys[source].add(key)
    if has_definition:
        keys[source].add(key)

with gzip.open(ROOT/'data/raw/brihat.json.gz', 'rt', encoding='utf-8') as f:
    brihat = json.load(f)
assert isinstance(brihat, list)
for i, row in enumerate(brihat):
    definitions = []
    for d in row['definitions']:
        definitions.append({'grammar': d.get('grammar'), 'etymology': d.get('etymology'),
                            'senses': [{'text': plain(s), 'source_html': s} for s in d.get('senses', [])]})
    add('brihat', i, row['word'], 'ne', definitions, row)

ltk = sqlite3.connect('file:'+str(ROOT/'data/raw/ltk.sqlite3')+'?mode=ro', uri=True)
assert ltk.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
ltk.row_factory = sqlite3.Row
examples = defaultdict(list)
for row in ltk.execute('SELECT * FROM example ORDER BY id'):
    examples[row['definition_id']].append(dict(row))
by_word = defaultdict(list)
for row in ltk.execute('SELECT * FROM definition ORDER BY id'):
    d = dict(row); d['examples'] = examples[d['id']]; by_word[d['word_id']].append(d)
for row in ltk.execute('SELECT * FROM word ORDER BY id'):
    record = dict(row); record['definitions'] = by_word[row['id']]
    definitions = [{'grammar': row['part_of_speech'], 'senses': [
        {'text': plain(d['value']), 'source_text': d['value'], 'examples': d['examples']}
        for d in record['definitions']]}]
    add('ltk', row['id'], row['value'], 'ne', definitions, record)
ltk.close()

with (ROOT/'data/raw/wiktionary.jsonl').open() as f:
    for i, line in enumerate(f):
        if not line.strip():
            continue
        row = json.loads(line)
        assert row.get('lang_code') == 'ne', (i, row.get('lang_code'))
        definitions = [{'grammar': row.get('pos'), 'etymology': row.get('etymology_text'), 'senses': [
            {'text': '; '.join(s.get('glosses', [])) if 'no-gloss' not in s.get('tags', []) else '',
             'tags': s.get('tags', []), 'examples': s.get('examples', []), 'form_of': s.get('form_of', [])}
            for s in row.get('senses', [])]}]
        add('wiktionary', i+1, row['word'], 'en', definitions, row)
c.commit()
assert c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'

# Group homographs under one lookup key, retaining independent source records/senses.
with gzip.open(OUT/'dictionary.jsonl.gz', 'wt', encoding='utf-8') as f:
    current = None; grouped = []; written = 0
    for source,sid,word,key,lang,defs in c.execute('SELECT source,source_record_id,headword,lookup_key,definition_language,definitions_json FROM entries ORDER BY lookup_key,source,id'):
        if current is not None and key != current:
            f.write(dump({'headword': current, 'entries': grouped})+'\n'); written += 1; grouped = []
        current = key
        grouped.append({'source': source, 'source_record_id': sid, 'original_headword': word,
                        'definition_language': lang, 'definitions': json.loads(defs)})
    if current is not None:
        f.write(dump({'headword': current, 'entries': grouped})+'\n'); written += 1
union_all = set().union(*allkeys.values()); union = set().union(*keys.values())
assert written == len(union_all)
assert c.execute('SELECT COUNT(*) FROM entries').fetchone()[0] == sum(counts.values())

# Surface forms only: Devanagari letters and combining marks; internal joiners retained.
# Digits, danda, punctuation, Latin text and isolated combining marks are excluded.
def words(text):
    buf = []
    for ch in unicodedata.normalize('NFC', text):
        dev = '\u0900' <= ch <= '\u097f' or '\ua8e0' <= ch <= '\ua8ff'
        cat = unicodedata.category(ch)
        if dev and (cat.startswith('L') or (cat.startswith('M') and buf)):
            buf.append(ch)
        elif ch in '\u200c\u200d' and buf:
            buf.append(ch)
        else:
            if buf:
                yield ''.join(buf).rstrip('\u200c\u200d'); buf = []
    if buf:
        yield ''.join(buf).rstrip('\u200c\u200d')

freq = Counter(); work_counts = Counter(); sample_works = defaultdict(list); archive = []; per_author = defaultdict(Counter)
for p in sorted((REPO/'archives/authors').glob('*/*/metadata.json')):
    meta = json.loads(p.read_text())
    if meta['rights']['status'] not in ('public-domain', 'permission-granted'):
        continue
    tp = p.parent/'text.txt'; data = tp.read_bytes(); text = data.decode('utf-8')
    wf = Counter(words(text)); freq.update(wf); per_author[meta['author']['id']].update(wf)
    rel = str(tp.relative_to(REPO))
    for w in wf:
        work_counts[w] += 1
        if len(sample_works[w]) < 3:
            sample_works[w].append(rel)
    archive.append({'path': rel, 'sha256': hashlib.sha256(data).hexdigest(), 'title': meta['title'],
                    'author': meta['author']['id'], 'tokens': sum(wf.values()), 'distinct_forms': len(wf),
                    'whitespace_tokens': len(text.split())})
assert archive and freq
relaxed_union = {relaxed(w) for w in union}
by_relaxed = defaultdict(set)
for w in union:
    by_relaxed[relaxed(w)].add(w)

def coverage(kset, corpus=freq):
    matched = corpus.keys() & kset
    return {'matched_forms': len(matched), 'total_forms': len(corpus),
            'distinct_coverage_pct': round(100*len(matched)/len(corpus), 2),
            'matched_tokens': sum(corpus[w] for w in matched), 'total_tokens': sum(corpus.values()),
            'token_coverage_pct': round(100*sum(corpus[w] for w in matched)/sum(corpus.values()), 2)}
source_summary = {s: {'records': counts[s], 'distinct_headwords': len(allkeys[s]),
                       'headwords_with_definitions': len(keys[s]), **coverage(keys[s]),
                       'headwords_unique_to_source': len(keys[s] - set().union(*(keys[t] for t in keys if t != s)))}
                  for s in counts}
relaxed_matched = {w for w in freq if relaxed(w) in relaxed_union}
report = {'method': 'NFC exact Devanagari surface-form lookup; Unicode whitespace normalized in dictionary headwords. No stemming, spelling modernization or fuzzy matching. Separate secondary match removes only ZWJ/ZWNJ.',
          'scope': 'Published work text.txt only; all included literary text, headings and notes count. Summaries, metadata and PDF/HTML sources excluded. Not a count of linguistic lemmas. Original texts remain unproofread and can contain OCR errors.',
          'works': len(archive), 'authors': len(per_author), 'tokens': sum(freq.values()), 'distinct_forms': len(freq),
          'whitespace_tokens': sum(a['whitespace_tokens'] for a in archive),
          'dictionary_records': sum(counts.values()), 'dictionary_headwords': len(union_all),
          'dictionary_headwords_with_definitions': len(union), 'sources': source_summary,
          'combined_exact': coverage(union), 'combined_ignore_joiners': coverage(relaxed_matched),
          'nepali_definitions_exact': coverage(keys['brihat'] | keys['ltk']),
          'headwords_shared_across_sources': sum(sum(w in allkeys[s] for s in allkeys)>1 for w in union_all),
          'per_author': {a: coverage(union,f) for a,f in per_author.items()},
          'limitations': ['Dictionary headwords include phrases; archive counts are individual written forms.',
                         'Entry matches do not establish that a sense fits the passage.',
                         'Unmatched forms include inflections, archaic spellings, names and OCR errors; they are not all missing dictionary lemmas.',
                         'The union retains source-specific licences and languages; no single licence is claimed and no redistribution is performed.']}
(OUT/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
(OUT/'archive_snapshot.json').write_text(json.dumps(archive, ensure_ascii=False, indent=2)+'\n')
with (OUT/'vocabulary.csv').open('w', newline='') as f, (OUT/'unmatched.csv').open('w', newline='') as missing:
    fields=['word','occurrences','works','exact_sources','joiner_only_candidates','sample_text_paths']
    writer=csv.writer(f); mw=csv.writer(missing); writer.writerow(fields); mw.writerow(fields)
    for w,n in freq.most_common():
        sources=[s for s in counts if w in keys[s]]
        alternatives=sorted(by_relaxed.get(relaxed(w),set())) if not sources else []
        row=[w,n,work_counts[w],';'.join(sources),';'.join(alternatives),';'.join(sample_works[w])]
        writer.writerow(row)
        if not sources: mw.writerow(row)
# Confirm no original was modified during the comparison.
for a in archive:
    assert hashlib.sha256((REPO/a['path']).read_bytes()).hexdigest() == a['sha256']
print(json.dumps({k:v for k,v in report.items() if k not in ('per_author','limitations')}, ensure_ascii=False, indent=2))
c.close()
