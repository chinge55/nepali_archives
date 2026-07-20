#!/usr/bin/env python3
"""
build_lexicon.py — Stage 1 data build (plan.md).

Inputs (data/, gitignored — see fetch commands in README of this dir):
  nep_train.json, nep_valid.json     Aksharantar-nep (JSONL). nep_test.json is
                                     NEVER read here: held out for Stage 3 eval.
  nep_news_2010_300K-words.txt       Leipzig Nepali news frequency list.
  nep_news_2010_300K-sentences.txt   Leipzig sentences (bigram source).
  ../../archives/authors/*/*/text.txt  archive corpus (register-matched freqs).

Outputs (build/, gitignored, reproducible):
  lexicon-core.json   top CORE_N words  (ships inline with the POC page)
  lexicon-full.json   top FULL_N words  (background fetch)
  bigram.json         word-bigram counts (wired in Stage 4)
  report.txt          filter stats, sizes, spot-check sample

Lexicon JSON:
  {"version":1,
   "words": [[devanagari, canonical_roman, score], ...],
   "keys":  {normkey: [word_index, ...] ranked best-first}}

Filtering: a pair is kept when the attested romanization agrees with our
key_romanize under normalize() (exact) or within a small edit distance —
this drops Aksharantar's glued-token and English-back-spelling noise
(reviews/04) on principle rather than by length heuristics.
Score: blended log frequency, archive corpus weighted over modern news
(register decision deferred to Stage 3; both raw counts kept in report).
"""
import json
import math
import shutil
import re
import sys
import gzip
from collections import Counter
from pathlib import Path

from translit_keys import key_romanize, normalize, word_keys

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent
DATA = PROJ / 'data'
BUILD = PROJ / 'build'
ARCHIVE = PROJ.parent / 'archives' / 'authors'

CORE_N = 5_000
FULL_N = 50_000
W_ARCHIVE, W_NEWS = 2.0, 1.0          # log-space blend (see docstring)
DEVA_RE = re.compile(r'^[\u0900-\u0963\u0971-\u097f]+$')
LATIN_RE = re.compile(r'^[a-z]+$')
DEVA_TOKEN = re.compile(r'[\u0900-\u0963\u0971-\u097f]+')


def edit_le(a, b, k):
    """True iff levenshtein(a,b) <= k (banded DP with early exit)."""
    if abs(len(a) - len(b)) > k:
        return False
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        lo = len(b) + 1
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            lo = min(lo, cur[j])
        if lo > k:
            return False
        prev = cur
    return prev[-1] <= k


def load_pairs():
    """Aksharantar train+valid -> {devanagari: attested_roman}, with filter stats."""
    stats = Counter()
    pairs = {}
    for name in ('nep_train.json', 'nep_valid.json'):
        with open(DATA / name, encoding='utf-8') as f:
            for line in f:
                row = json.loads(line)
                deva = row['native word'].strip()
                eng = row['english word'].strip().lower()
                stats['rows'] += 1
                if not DEVA_RE.match(deva) or not LATIN_RE.match(eng):
                    stats['drop_charset'] += 1
                    continue
                canon_n = normalize(key_romanize(deva))
                eng_n = normalize(eng)
                if canon_n == eng_n:
                    stats['agree_exact'] += 1
                elif eng_n in word_keys(deva):
                    stats['agree_alias'] += 1
                elif edit_le(canon_n, eng_n, max(1, len(canon_n) // 5)):
                    stats['agree_near'] += 1
                else:
                    stats['drop_disagree'] += 1   # glued tokens, loanword back-spellings
                    continue
                pairs[deva] = eng
    return pairs, stats


def archive_counts():
    c = Counter()
    for txt in ARCHIVE.glob('*/*/text.txt'):
        for w in DEVA_TOKEN.findall(txt.read_text(encoding='utf-8')):
            c[w] += 1
    return c


def news_counts():
    c = Counter()
    with open(DATA / 'nep_news_2010_300K-words.txt', encoding='utf-8') as f:
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if len(parts) >= 3 and DEVA_RE.match(parts[1]):
                c[parts[1]] += int(parts[2])
    return c


def bigrams(arch_c):
    big = Counter()

    def feed(tokens):
        for a, b in zip(tokens, tokens[1:]):
            big[(a, b)] += 1

    for txt in ARCHIVE.glob('*/*/text.txt'):
        for line in txt.read_text(encoding='utf-8').splitlines():
            feed(DEVA_TOKEN.findall(line))
    with open(DATA / 'nep_news_2010_300K-sentences.txt', encoding='utf-8') as f:
        for line in f:
            feed(DEVA_TOKEN.findall(line))
    # prune: count>=3, top 50 followers per head
    byhead = {}
    for (a, b), n in big.items():
        if n >= 3:
            byhead.setdefault(a, []).append((b, n))
    return {a: dict(sorted(fs, key=lambda x: -x[1])[:50]) for a, fs in byhead.items()}


def main():
    BUILD.mkdir(exist_ok=True)
    print('loading Aksharantar…', flush=True)
    pairs, stats = load_pairs()
    print(f'  kept {len(pairs):,} unique words '
          f'(exact {stats["agree_exact"]:,} / alias {stats["agree_alias"]:,} / '
          f'near {stats["agree_near"]:,}; dropped charset {stats["drop_charset"]:,}, '
          f'disagree {stats["drop_disagree"]:,})', flush=True)

    print('counting frequencies…', flush=True)
    arch_c, news_c = archive_counts(), news_counts()

    vocab = set(pairs) | {w for w, n in arch_c.items() if n >= 2} \
                       | {w for w, n in news_c.items() if n >= 5}

    def score(w):
        return W_ARCHIVE * math.log1p(arch_c.get(w, 0)) + W_NEWS * math.log1p(news_c.get(w, 0))

    # corpus-attested words first; Aksharantar-only words get a tiny floor score
    ranked = sorted(vocab, key=lambda w: (-score(w), w))
    with_freq = [w for w in ranked if score(w) > 0]
    akshar_only = [w for w in ranked if score(w) == 0]
    ordered = with_freq + akshar_only
    print(f'  vocab {len(vocab):,} (freq-attested {len(with_freq):,})', flush=True)

    def emit(n, path):
        sel = ordered[:n]
        words, keys = [], {}
        for idx, w in enumerate(sel):
            words.append([w, key_romanize(w), round(score(w), 2)])
            for k in word_keys(w, pairs.get(w)):
                keys.setdefault(k, []).append(idx)
        # per-key ranking is score order == index order already (ordered list)
        obj = {'version': 1, 'words': words, 'keys': keys}
        raw = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode()
        path.write_bytes(raw)
        gz = len(gzip.compress(raw, 9))
        print(f'  {path.name}: {len(sel):,} words, {len(keys):,} keys, '
              f'{len(raw)/1e6:.2f} MB raw / {gz/1e6:.2f} MB gz', flush=True)
        return gz

    print('emitting lexicons…', flush=True)
    emit(CORE_N, BUILD / 'lexicon-core.json')
    emit(FULL_N, BUILD / 'lexicon-full.json')

    print('building english pass-through list…', flush=True)
    # google-10000-english minus words that collide with common Nepali
    # romanizations (their normalize key is a core-lexicon key): 'man' मन,
    # 'ho' हो, 'ban' वन must stay Nepali-first; 'school', 'reply' stay English.
    core_keys = set()
    for w in ordered[:CORE_N]:
        core_keys |= word_keys(w, pairs.get(w))
    eng = []
    with open(DATA / 'google-10000-english-no-swears.txt', encoding='utf-8') as f:
        for line in f:
            w = line.strip().lower()
            if len(w) >= 2 and LATIN_RE.match(w) and normalize(w) not in core_keys:
                eng.append(w)
    raw = json.dumps({'version': 1, 'words': eng}, separators=(',', ':')).encode()
    (BUILD / 'english.json').write_bytes(raw)
    print(f'  english.json: {len(eng):,} words kept of 10k, '
          f'{len(raw)/1e3:.0f} KB raw / {len(gzip.compress(raw, 9))/1e3:.0f} KB gz', flush=True)

    print('building bigrams…', flush=True)
    big = bigrams(arch_c)
    raw = json.dumps(big, ensure_ascii=False, separators=(',', ':')).encode()
    (BUILD / 'bigram.json').write_bytes(raw)
    print(f'  bigram.json: {len(big):,} heads, {len(raw)/1e6:.2f} MB raw / '
          f'{len(gzip.compress(raw, 9))/1e6:.2f} MB gz', flush=True)

    # report + spot-check sample
    import random
    random.seed(20260720)
    sample = random.sample(ordered[:FULL_N], 100)
    with open(BUILD / 'report.txt', 'w', encoding='utf-8') as f:
        f.write(f'filter stats: {dict(stats)}\n')
        f.write(f'vocab {len(vocab)}  freq-attested {len(with_freq)}\n\n')
        f.write('spot-check (word / canon / keys / arch / news):\n')
        for w in sample:
            f.write(f'{w}\t{key_romanize(w)}\t{sorted(word_keys(w, pairs.get(w)))}'
                    f'\t{arch_c.get(w, 0)}\t{news_c.get(w, 0)}\n')
    print('report -> build/report.txt')

    if '--install' in sys.argv:
        # vendor the shipped artifacts into the site's tracked assets (see
        # build_site.write_type_page: CI can't rebuild these, so they're tracked)
        adir = PROJ.parent / 'assets' / 'type'
        for fn in ('lexicon-core.json', 'lexicon-full.json', 'english.json'):
            shutil.copy(BUILD / fn, adir / fn)
        print(f'installed lexicons -> {adir}')


if __name__ == '__main__':
    main()
