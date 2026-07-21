"""Surya-2 engine — the VLM reader (datalab-to/surya-ocr-2, 650M).

Runs through the surya CLI from its own conda env, on the llama.cpp/Vulkan
backend (see config.py for why not vLLM). The CLI accepts a whole folder in
one invocation and keeps its model server warm (--keep_server), so batch
cost is one model load + ~seconds per page.

Output parsing: for a folder input surya writes ONE results.json under
<out>/<folder_name>/, keyed by page stem, with layout blocks of HTML;
we flatten those to plain text lines, preserving reading order.
"""
from __future__ import annotations

import html
import json
import re
import subprocess
from pathlib import Path

from ..config import settings
from .base import OcrEngine

_TAG = re.compile(r"<[^>]+>")
_BR = re.compile(r"<br\s*/?>")


def blocks_to_text(page: dict) -> str:
    """Flatten one page's surya blocks into plain text."""
    lines: list[str] = []
    for block in page.get("blocks", []):
        raw = block.get("html") or block.get("text") or ""
        raw = _BR.sub("\n", raw)
        raw = _TAG.sub("", raw)
        text = html.unescape(raw).strip("\n")
        if text.strip():
            lines.append(text)
    return "\n".join(lines) + "\n"


class SuryaEngine(OcrEngine):
    name = "surya"

    def available(self) -> tuple[bool, str]:
        if not settings.surya_bin.exists():
            return False, f"surya CLI not found: {settings.surya_bin}"
        if not settings.llama_cpp_binary.exists():
            return False, f"llama-server not found: {settings.llama_cpp_binary}"
        return True, f"{settings.surya_bin} (llamacpp backend)"

    def ocr_pages(self, images: list[Path], out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        raw_dir = out_dir / "_surya_raw"
        folder = images[0].parent
        # one CLI call for the whole pages folder; the model server stays warm
        subprocess.run(
            [str(settings.surya_bin), str(folder),
             "--output_dir", str(raw_dir), "--keep_server"],
            check=True, capture_output=True, env=settings.surya_env())
        results_json = raw_dir / folder.name / "results.json"
        if not results_json.exists():
            raise RuntimeError(f"surya wrote no results.json under {raw_dir}")
        results = json.loads(results_json.read_text(encoding="utf-8"))
        for image in images:
            pages = results.get(image.stem)
            if not pages:
                raise RuntimeError(f"surya produced no result for {image.name}")
            (out_dir / f"{image.stem}.txt").write_text(
                blocks_to_text(pages[0]), encoding="utf-8")
