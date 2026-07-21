"""Tesseract engine — the fast classical baseline (lang `nep`).

Cheap enough to always run: its value in the ensemble is that it fails
differently from the VLM engines (e.g. it reads झैँ correctly where Surya-2
confuses झ→क), so agreement between the two is strong evidence of a correct
line.
"""
from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..config import settings
from .base import OcrEngine


class TesseractEngine(OcrEngine):
    name = "tesseract"

    def available(self) -> tuple[bool, str]:
        binary = settings.tesseract_bin
        if not binary.exists():
            return False, f"binary not found: {binary}"
        try:
            version = subprocess.run(
                [str(binary), "--version"], capture_output=True, text=True,
                timeout=10).stdout.splitlines()[0]
        except Exception as exc:  # noqa: BLE001 — availability must not raise
            return False, f"{binary}: {exc}"
        return True, version

    def ocr_pages(self, images: list[Path], out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)

        def one(image: Path) -> None:
            subprocess.run(
                [str(settings.tesseract_bin), str(image),
                 str(out_dir / image.stem), "-l", settings.tesseract_lang],
                check=True, capture_output=True)

        # tesseract is single-threaded per page; parallelize across pages
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(one, images))
