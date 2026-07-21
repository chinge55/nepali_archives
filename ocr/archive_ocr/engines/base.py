"""Engine interface. An engine turns page images into page text files.

Engines work on a whole directory of pages at once (some, like Surya, are
dramatically faster in batch because a model server stays warm between
pages). Output contract: one UTF-8 `<stem>.txt` per input `<stem>.png` in
`out_dir`. Anything else an engine writes is its own business.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class OcrEngine(ABC):
    """A source of page text. Implementations live beside this module and
    register themselves in engines/__init__.py."""

    name: str

    @abstractmethod
    def available(self) -> tuple[bool, str]:
        """(usable, human-readable detail) — never raises."""

    @abstractmethod
    def ocr_pages(self, images: list[Path], out_dir: Path) -> None:
        """Read every image, writing <stem>.txt files into out_dir."""
