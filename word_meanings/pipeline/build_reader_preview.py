#!/usr/bin/env python3
"""Build a local full-work dictionary preview, without changing literary sources."""
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import sqlite3
import shutil
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
OUT = ROOT / 'data/preview'
WORK = REPO / 'archives/authors/devkota/munamadan'


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
                yield ''.join(buf).rstrip('\u200c\u200d')
                buf = []
    if buf:
        yield ''.join(buf).rstrip('\u200c\u200d')


def main():
    original = (WORK / 'text.txt').read_bytes()
    text = original.decode('utf-8')
    meta = json.loads((WORK / 'metadata.json').read_text())
    associations = json.loads((ROOT / 'data/review/lookup-associations.json').read_text())
    sources = {s['id']: s for s in json.loads((ROOT / 'sources.json').read_text())}
    labels = {'brihat': 'बृहत् नेपाली शब्दकोश', 'ltk': 'नेपाली समसामयिक शब्दकोश (LTK)',
              'wiktionary': 'Wiktionary (नेपाली → English)'}
    counts = Counter(words(text))
    c = sqlite3.connect(f'file:{ROOT / "data/combined/dictionary.sqlite3"}?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    cache = {}

    def entries(headword):
        if headword not in cache:
            cache[headword] = []
            for row in c.execute('SELECT * FROM entries WHERE lookup_key=? AND has_definition=1 ORDER BY id', (headword,)):
                groups = []
                for g in json.loads(row['definitions_json']):
                    groups.append({k: g[k] for k in ('grammar', 'etymology') if g.get(k)})
                    groups[-1]['senses'] = [{k: s[k] for k in ('text', 'examples', 'tags', 'form_of') if k in s}
                                            for s in g['senses']]
                cache[headword].append({'id': f'{row["source"]}:{row["source_record_id"]}',
                    'headword': row['headword'], 'source': row['source'], 'label': labels[row['source']],
                    'sourceUrl': sources[row['source']]['repository'], 'language': row['definition_language'],
                    'groups': groups})
        return cache[headword]

    lookup = {}
    coverage = Counter()
    for form in sorted(counts):
        direct = entries(form)
        association = associations.get(form)
        if direct:
            kind, headwords, found, explanation = 'exact', [form], direct, ''
        elif association:
            kind, headwords = association['kind'], association['headwords']
            assert kind in ('reviewed_association', 'unicode_joiner_equivalent')
            found = [entry for headword in headwords for entry in entries(headword)]
            explanation = association.get('explanation', '')
        else:
            coverage['unavailable_forms'] += 1
            coverage['unavailable_tokens'] += counts[form]
            continue
        assert found, form
        lookup[form] = {'kind': kind, 'headwords': headwords, 'entries': found, 'explanation': explanation}
        coverage[kind + '_forms'] += 1
        coverage[kind + '_tokens'] += counts[form]

    contexts = []
    for word, line, sense, expected in [
        ('अम्लान', 'कल्पने माली, अम्लान कुसुम,', 0, 'नओइलाएको'),
        ('कुसुम', 'कल्पने माली, अम्लान कुसुम,', 1, 'फूल; पुष्प'),
        ('पल्लव', 'चरीले तर चुच्चाले च्यापी पहिलो पल्लव,', 2, 'नयाँ निस्केको पात'),
    ]:
        assert line in text.splitlines()
        target = next(e for e in lookup[word]['entries'] if e['source'] == 'brihat')
        assert expected in target['groups'][0]['senses'][sense]['text']
        contexts.append({'word': word, 'line': line, 'source': 'brihat',
                         'entryId': target['id'], 'groupIndex': 0, 'senseIndex': sense})

    stats = {'total_forms': len(counts), 'total_tokens': sum(counts.values()),
             'available_forms': len(lookup), 'available_tokens': sum(counts[w] for w in lookup),
             **coverage}
    stats['available_token_pct'] = round(100 * stats['available_tokens'] / stats['total_tokens'], 2)
    payload = {'title': meta['title'], 'author': meta['author']['name'], 'text': text,
        'textSha256': hashlib.sha256(original).hexdigest(), 'words': lookup,
        'contextSenses': contexts, 'stats': stats,
        'scope': 'Local evaluation. Dictionary lookup availability is not proofreading or contextual-sense accuracy.'}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'work.json').write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n')
    (OUT / 'text.txt').write_bytes(original)
    template = (ROOT / 'preview/index.template.html').read_text()
    for filename in ['app.js', 'styles.css']:
        shutil.copyfile(ROOT / 'preview' / filename, OUT / filename)
    assert template.count('<!-- ORIGINAL_TEXT -->') == 1
    (OUT / 'index.html').write_text(template.replace('<!-- ORIGINAL_TEXT -->', '<div class="original-text">' + html.escape(text) + '</div>'))
    assert (OUT / 'text.txt').read_bytes() == original
    report = {'work': str(WORK.relative_to(REPO)), 'text_sha256': payload['textSha256'],
        'json_bytes': (OUT / 'work.json').stat().st_size, 'stats': stats,
        'context_reviewed_passages': len(contexts), 'source_files_changed': False}
    (ROOT / 'data/review/reader-preview-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
