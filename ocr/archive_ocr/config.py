"""Environment-driven configuration for the OCR infrastructure.

Every path can be overridden with an environment variable so the same code
runs on any machine. Defaults match this workstation (see ocr/README.md):
big artifacts (jobs, model weights) live on the free disk, never in ~.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_FREE_DISK = Path("/mnt/disk_sda2/sangam")


def _env_path(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, str(default))).expanduser()


@dataclass(frozen=True)
class Settings:
    """All knobs in one place. Instantiate once (see `settings` below)."""

    # Where job artifacts live: jobs/<job_id>/{source.pdf, job.json, pages/, ocr/}
    work_dir: Path = field(
        default_factory=lambda: _env_path("OCR_WORK_DIR", _FREE_DISK / "ocr_jobs"))

    # Gold-standard pages (tracked in git): gold/<book>/pg-NNN.txt
    gold_dir: Path = field(
        default_factory=lambda: _env_path(
            "OCR_GOLD_DIR", Path(__file__).resolve().parent.parent / "gold"))

    # Page rendering
    dpi: int = field(default_factory=lambda: int(os.environ.get("OCR_DPI", "300")))

    # Engine binaries. Engines whose binaries are missing report unavailable
    # instead of crashing the server.
    tesseract_bin: Path = field(
        default_factory=lambda: _env_path(
            "TESSERACT_BIN",
            Path("~/miniconda3/envs/archive_env/bin/tesseract")))
    tesseract_lang: str = field(
        default_factory=lambda: os.environ.get("TESSERACT_LANG", "nep"))

    # The ensemble formula's roles. Swapping the base model (e.g. a future
    # Surya-3 or CHURRO engine module) is a config change, not a code change.
    primary_engine: str = field(
        default_factory=lambda: os.environ.get("OCR_PRIMARY_ENGINE", "surya"))
    shadow_engine: str = field(
        default_factory=lambda: os.environ.get("OCR_SHADOW_ENGINE", "tesseract"))

    surya_bin: Path = field(
        default_factory=lambda: _env_path(
            "SURYA_BIN", Path("~/miniconda3/envs/surya_env/bin/surya_ocr")))
    # Surya runs its VLM through llama.cpp (Vulkan build) — the vLLM/docker
    # path needs CUDA >= 13 which this machine's driver does not provide.
    llama_cpp_binary: Path = field(
        default_factory=lambda: _env_path(
            "LLAMA_CPP_BINARY", _FREE_DISK / "tools/llama-b10075/llama-server"))
    hf_home: Path = field(
        default_factory=lambda: _env_path(
            "HF_HOME", _FREE_DISK / "model_cache/huggingface"))

    def surya_env(self) -> dict[str, str]:
        """Environment for spawning the surya CLI (llama.cpp backend)."""
        env = dict(os.environ)
        env.update({
            "SURYA_INFERENCE_BACKEND": "llamacpp",
            "LLAMA_CPP_BINARY": str(self.llama_cpp_binary),
            "LD_LIBRARY_PATH": str(self.llama_cpp_binary.parent),
            "HF_HOME": str(self.hf_home),
        })
        return env


settings = Settings()
