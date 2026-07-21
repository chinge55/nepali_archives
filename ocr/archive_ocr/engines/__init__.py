"""Engine registry. Adding an engine = one module + one line here."""
from __future__ import annotations

from .base import OcrEngine
from .ensemble import EnsembleEngine
from .surya import SuryaEngine
from .tesseract import TesseractEngine

ENGINES: dict[str, OcrEngine] = {
    engine.name: engine
    for engine in (TesseractEngine(), SuryaEngine(), EnsembleEngine())
}


def get_engine(name: str) -> OcrEngine:
    try:
        return ENGINES[name]
    except KeyError:
        raise KeyError(
            f"unknown engine {name!r}; available: {', '.join(ENGINES)}") from None
