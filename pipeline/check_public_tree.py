#!/usr/bin/env python3
"""Enforce the repository's public-source privacy boundary.

This is deliberately structural: public files describe capabilities and
reproducible behavior, while credentials, concrete execution bindings,
workstation paths, and deployment notes remain local.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PRIVATE_BASENAMES = {
    ".env",
    "agent_profiles.local.json",
    "generation.local.yaml",
    "local_paths.json",
    "DEPLOY_NOTES.md",
    "id_ed25519",
    "id_rsa",
}
MACHINE_PATH = re.compile(r"(?i)(?:[A-Z]:\\Users\\|/home/|/Users/|/mnt/)")
SECRET_VALUE = re.compile(
    r"(?:-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----|"
    r"\bsk-[A-Za-z0-9_-]{20,}\b|"
    r"\bgithub_pat_[A-Za-z0-9_]{20,}\b|"
    r"\bgh[pousr]_[A-Za-z0-9]{20,}\b|"
    r"https?://[^/\s:@]{2,}:[^/\s@]{4,}@)"
)
PRIVATE_GENERATION_KEY = re.compile(r"^\s*(?:model|endpoint)\s*:", re.MULTILINE)


def tracked_paths() -> list[Path]:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [ROOT / item.decode("utf-8", "surrogateescape")
            for item in raw.split(b"\0") if item]


def main() -> int:
    problems: list[str] = []
    paths = tracked_paths()

    for path in paths:
        rel = path.relative_to(ROOT)
        if path.name in PRIVATE_BASENAMES:
            problems.append(f"private local file is tracked: {rel}")
        if rel == Path("pipeline/check_public_tree.py"):
            continue
        if not path.is_file() or path.stat().st_size > 5_000_000:
            continue
        data = path.read_bytes()
        if b"\0" in data[:8192]:
            continue
        text = data.decode("utf-8", "replace")
        if MACHINE_PATH.search(text):
            problems.append(f"workstation path in public file: {rel}")
        if SECRET_VALUE.search(text):
            problems.append(f"possible credential in public file: {rel}")

    profiles_path = ROOT / "ocr" / "agent_profiles.json"
    profiles = json.loads(profiles_path.read_text(encoding="utf-8"))
    for profile_name, bindings in profiles.get("profiles", {}).items():
        for capability, binding in bindings.items():
            if isinstance(binding, dict) and binding.get("model"):
                problems.append(
                    "concrete agent binding in public profile: "
                    f"{profile_name}.{capability}"
                )

    generation_path = ROOT / "horoscope" / "generation.yaml"
    if PRIVATE_GENERATION_KEY.search(generation_path.read_text(encoding="utf-8")):
        problems.append("private endpoint/model key in horoscope/generation.yaml")

    if problems:
        print("public-tree hygiene failed:")
        for problem in sorted(set(problems)):
            print(f"- {problem}")
        return 1
    print(f"public-tree hygiene passed ({len(paths)} tracked paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
