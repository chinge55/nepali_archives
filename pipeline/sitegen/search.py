"""Deterministic title index and Roman-to-Devanagari search bridge."""

import json


def write_search_data(
    context,
    search_rows,
    word_counts,
    *,
    normalize_key,
    translit_word_keys,
):
    (context.site / "search-index.json").write_text(
        json.dumps(
            {"works": search_rows},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    roman_map = {}
    for word in word_counts:
        keys = translit_word_keys(word)
        primary = normalize_key(word)
        for roman in keys:
            if roman:
                roman_map.setdefault(roman, {})[word] = roman != primary

    shards = {}
    for roman in sorted(roman_map):
        words = roman_map[roman]
        shard = (
            roman[0].lower()
            if roman[:1].isalpha()
            else "_"
        )
        ranked = sorted(
            words,
            key=lambda word: (
                words[word],
                -word_counts[word],
                word,
            ),
        )
        shards.setdefault(shard, {})[roman] = ranked[:12]

    output = context.site / "searchroman"
    output.mkdir(exist_ok=True)
    for shard in sorted(shards):
        (output / f"{shard}.json").write_text(
            json.dumps(
                shards[shard],
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
