#!/usr/bin/env python3
"""
translit_keys.py — normalization keys for the Roman→Devanagari lexicon.

Two functions define the lookup contract (literature_review.md §2 layer 3):

  key_romanize(devanagari_word) -> canonical Roman
      devanagari_slug.romanize() with ONE change: chandrabindu ँ maps to 'n'
      (the slug drops it, but typists write it: सँगै -> "sangai").

  normalize(roman) -> lookup key
      Strictly coarser than key_romanize: folds every distinction informal
      typists don't reliably make, so normalize(user_input) and
      normalize(key_romanize(word)) provably land on the same key.
      Folds: c/ch/chh/x -> one affricate class; sh->s; w/v->b; ph/f -> one;
      z->j; gy->ज्ञ-class; ee->i, oo->u; any doubled letter run -> one;
      one word-final 'a' (schwa) stripped.

Ranking (NOT normalization) restores fine distinctions via frequency and
surface hints — see the engine. Keep this file in sync with the JS port
(poc/engine.js normalize()); test_normalize.py is the shared spec.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'pipeline'))
import devanagari_slug as _slug

# key variant of the slug scheme: typists write the nasal that ँ marks
_slug.SIGN['ँ'] = 'n'


def key_romanize(word):
    """Devanagari word -> canonical Roman (lexicon side)."""
    return _slug.romanize(word)


# One left-to-right pass, longest alternative first at each position.
_SUB = {
    'ksh': 'kC',   # क्ष
    'chh': 'C',    # छ
    'ch': 'C',     # च/छ merged: one affricate class
    'gy': 'J',     # ज्ञ / ग्य class ('gya' NOT folded whole: keep the vowel)
    'sh': 's',     # श/ष -> स class
    'ph': 'P',     # फ
    'ee': 'i',     # long-vowel spellings (before run-collapse, which would give 'e')
    'oo': 'u',
    'c': 'C',
    'x': 'C',      # chat shorthand for छ (क्ष typed 'x' won't key-match; lexicon alias covers it)
    'f': 'P',
    'z': 'j',
    'w': 'b',      # व/ब both read /b/ (slug already maps व->b)
    'v': 'b',
    'q': 'k',
}
_SUB_RE = re.compile('|'.join(sorted(_SUB, key=len, reverse=True)))
_RUN_RE = re.compile(r'(.)\1+')


def normalize(s):
    """Roman string (user input OR key_romanize output) -> lookup key."""
    s = s.lower()
    s = re.sub(r'[^a-z]+', ' ', s)
    out = []
    for w in s.split():
        w = _SUB_RE.sub(lambda m: _SUB[m.group(0)], w)
        w = _RUN_RE.sub(r'\1', w)          # naam->nam, tti->ti, kiii->ki
        if len(w) > 1 and w.endswith('a'):  # final schwa carries no signal
            w = w[:-1]
        out.append(w)
    return ' '.join(out)


_VOWELS = set('aeiou')


def _schwa_variants(roman):
    """Medial-schwa deletion variants of a canonical romanization.

    देवकोटा -> 'debakota': speakers say deb-ko-ta, typists write 'devkota'.
    Which medial schwas delete is irregular (review 05 §5.1), so the lexicon
    carries alias keys for each single deletion plus the all-deleted form.
    """
    idxs = [i for i in range(1, len(roman) - 1)
            if roman[i] == 'a'
            and roman[i - 1] not in _VOWELS and roman[i + 1] not in _VOWELS]
    variants = set()
    for i in idxs:
        variants.add(roman[:i] + roman[i + 1:])
    if len(idxs) > 1:
        variants.add(''.join(c for j, c in enumerate(roman) if j not in idxs))
    return variants


def word_keys(deva, english=None):
    """All lookup keys a Devanagari word is filed under (the build contract):
    primary key + medial-schwa alias keys + the attested romanization's key."""
    canon = key_romanize(deva)
    keys = {normalize(canon)}
    for v in _schwa_variants(canon):
        keys.add(normalize(v))
    if english:
        keys.add(normalize(english))
    # क्ष normalizes to 'kC' but chat typists write bare 'x' (लक्ष्मी -> laxmi -> 'laCmi')
    for k in [k for k in keys if 'kC' in k]:
        keys.add(k.replace('kC', 'C'))
    return keys


if __name__ == '__main__':
    for a in sys.argv[1:]:
        if re.search(r'[ऀ-ॿ]', a):
            r = key_romanize(a)
            print(f'{a} -> {r} -> {normalize(r)}')
        else:
            print(f'{a} -> {normalize(a)}')
