"""Nepali vocabulary check, borrowed from the transliteration project.

The /type/ tool's lexicon (50k corpus-attested words) doubles as an OCR
sanity check: a token no Nepali text ever produced (कैं, रुल्कन्छन्) is a
likely misread. Used to ANNOTATE review items — never to auto-correct
(real-word errors exist, and the archive preserves archaic spellings that
any modern wordlist under-covers).
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

_DEFAULT_LEXICON = (Path(__file__).resolve().parent.parent.parent
                    / "assets" / "type" / "lexicon-full.json")
_TOKEN = re.compile(r"[ऀ-ॣॱ-ॿ]{2,}")


@lru_cache(maxsize=1)
def _vocab() -> frozenset[str]:
    path = Path(os.environ.get("OCR_LEXICON", str(_DEFAULT_LEXICON)))
    if not path.exists():
        return frozenset()          # annotation quietly disabled
    data = json.loads(path.read_text(encoding="utf-8"))
    return frozenset(entry[0] for entry in data["words"])


def oov_tokens(line: str) -> list[str]:
    """Devanagari tokens of `line` that the lexicon has never seen."""
    vocab = _vocab()
    if not vocab:
        return []
    return [t for t in _TOKEN.findall(line) if t not in vocab]
