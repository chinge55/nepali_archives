"""Portable, environment-driven configuration for the OCR infrastructure."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

_OCR_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _OCR_ROOT.parent
_CACHE_ROOT = Path(
    os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
).expanduser()


def _read_local_paths() -> dict[str, str]:
    """Load ignored workstation paths without publishing them in source."""
    path = _OCR_ROOT / "local_paths.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        key: value
        for key, value in data.items()
        if isinstance(key, str) and isinstance(value, str) and value
    }


_LOCAL_PATHS = _read_local_paths()


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name) or _LOCAL_PATHS.get(name) or str(default)
    return Path(value).expanduser()


def _default_agent_profiles() -> Path:
    local = _OCR_ROOT / "agent_profiles.local.json"
    return local if local.is_file() else _OCR_ROOT / "agent_profiles.json"


@dataclass(frozen=True)
class Settings:
    """All knobs in one place. Instantiate once (see `settings` below)."""

    # Where job artifacts live: jobs/<job_id>/{source.pdf, job.json, pages/, ocr/}
    work_dir: Path = field(
        default_factory=lambda: _env_path(
            "OCR_WORK_DIR", _REPO_ROOT / ".ocr-work" / "jobs"))

    # Gold-standard pages (tracked in git): gold/<book>/pg-NNN.txt
    gold_dir: Path = field(
        default_factory=lambda: _env_path(
            "OCR_GOLD_DIR", Path(__file__).resolve().parent.parent / "gold"))

    # Page rendering
    dpi: int = field(default_factory=lambda: int(os.environ.get("OCR_DPI", "300")))

    # Optional private capability bindings for the book workflow's agent tasks.
    # The tracked fallback contains provider-neutral effort defaults only.
    agent_profiles_path: Path = field(
        default_factory=lambda: _env_path(
            "OCR_AGENT_PROFILES", _default_agent_profiles()))
    # Overrides the bindings file's active profile name.
    agent_profile: str = field(
        default_factory=lambda: os.environ.get("OCR_AGENT_PROFILE", ""))

    # Engine binaries. Engines whose binaries are missing report unavailable
    # instead of crashing the server.
    tesseract_bin: Path = field(
        default_factory=lambda: _env_path(
            "TESSERACT_BIN",
            Path("~/miniconda3/envs/archive_env/bin/tesseract")))
    tesseract_lang: str = field(
        default_factory=lambda: os.environ.get("TESSERACT_LANG", "nep"))

    # The ensemble formula's roles. Swapping the base engine (e.g. a future
    # Surya-3 or CHURRO engine module) is a config change, not a code change.
    primary_engine: str = field(
        default_factory=lambda: os.environ.get("OCR_PRIMARY_ENGINE", "surya"))
    shadow_engine: str = field(
        default_factory=lambda: os.environ.get("OCR_SHADOW_ENGINE", "tesseract"))

    surya_bin: Path = field(
        default_factory=lambda: _env_path(
            "SURYA_BIN", Path("~/miniconda3/envs/surya_env/bin/surya_ocr")))
    # Surya runs its vision-language engine through llama.cpp (Vulkan build);
    # alternative GPU deployments may require a newer CUDA stack.
    llama_cpp_binary: Path = field(
        default_factory=lambda: _env_path(
            "LLAMA_CPP_BINARY",
            _CACHE_ROOT / "nepali-archives" / "llama" / "llama-server"))
    hf_home: Path = field(
        default_factory=lambda: _env_path(
            "HF_HOME", _CACHE_ROOT / "huggingface"))

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
