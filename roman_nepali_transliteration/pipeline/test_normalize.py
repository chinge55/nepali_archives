#!/usr/bin/env python3
"""
test_normalize.py — the spec for the normalization/keying contract.

Property groups:
  1. Variant sets: every way a typist plausibly writes a word lands on ONE key.
  2. Meet pairs: normalize(typed) must be in word_keys(devanagari[, attested]) —
     the guarantee that a query finds its word in the lexicon. `attested` mimics
     the romanization the build harvests from Aksharantar for that word.
Run: python3 pipeline/test_normalize.py   (exit 0 = pass)
Keep in sync with the JS port's tests.
"""
from translit_keys import normalize, word_keys

# 1. spelling variants that must collide on one key
VARIANT_SETS = [
    ['nam', 'naam', 'naama'],                       # नाम
    ['cha', 'chha', 'xa'],                          # छ
    ['sabda', 'shabda'],                            # शब्द
    ['gyan', 'gyaan', 'gyana'],                     # ज्ञान
    ['kasto', 'kasTo', 'kastto'],                   # कस्तो
    ['hunchha', 'huncha', 'hunxa'],                 # हुन्छ
    ['ramro', 'raamro', 'ramrro'],                  # राम्रो
    ['bakil', 'wakil', 'vakil'],                    # वकिल
    ['pheri', 'feri', 'pherii'],                    # फेरि
    ['sathi', 'saathee', 'saathi'],                 # साथी
    ['garchhan', 'garchan', 'garxan'],              # गर्छन्
    ['prithbi', 'prithvi', 'prithwi'],              # पृथ्वी
    ['basanta', 'wasanta', 'vasanta'],              # वसन्त
]

# 2. (devanagari, typed, attested-romanization-or-None) — query must find word
MEET_PAIRS = [
    ('नाम', 'naam', None),
    ('नाम', 'nam', None),
    ('मेरो', 'mero', None),
    ('हो', 'ho', None),
    ('छ', 'chha', None),
    ('छ', 'xa', None),
    ('सँगै', 'sangai', None),        # chandrabindu typed as n (key_romanize patch)
    ('हुन्छ', 'hunchha', None),
    ('ज्ञान', 'gyan', None),
    ('क्षमा', 'kshama', None),
    ('शब्द', 'sabda', None),
    ('वसन्त', 'basant', None),       # conjunct-final schwa typed or not
    ('वसन्त', 'basanta', None),
    ('राम्रो', 'ramro', None),
    ('गर्छ', 'garchha', None),
    ('गर्छ', 'garcha', None),
    ('माया', 'maya', None),
    ('माया', 'maayaa', None),
    ('पानी', 'pani', None),
    ('पानी', 'paanee', None),
    ('नेपाल', 'nepal', None),
    ('नेपाली', 'nepali', None),
    ('कविता', 'kabita', None),
    ('कविता', 'kavita', None),
    ('पृथ्वी', 'prithvi', None),
    ('फेरि', 'pheri', None),
    ('फेरि', 'feri', None),
    ('साथी', 'sathi', None),
    ('मुना', 'muna', None),
    ('मदन', 'madan', None),
    ('पागल', 'pagal', None),
    ('देवकोटा', 'devkota', None),    # medial schwa deletion -> alias key
    ('देवकोटा', 'debkota', None),
    ('लक्ष्मी', 'laxmi', None),       # x as क्ष: kC->C alias key
    ('लक्ष्मी', 'lakshmi', None),
]


def main():
    bad = []
    for group in VARIANT_SETS:
        keys = {v: normalize(v) for v in group}
        if len(set(keys.values())) != 1:
            bad.append(f'variant set diverges: {keys}')
    for deva, typed, attested in MEET_PAIRS:
        keys = word_keys(deva, attested)
        q = normalize(typed)
        if q not in keys:
            bad.append(f'{deva} keys={sorted(keys)}  MISSES  {typed!r} -> {q!r}')
    if bad:
        print('FAIL')
        for b in bad:
            print(' ', b)
        raise SystemExit(1)
    print(f'OK: {len(VARIANT_SETS)} variant sets, {len(MEET_PAIRS)} meet pairs')


if __name__ == '__main__':
    main()
