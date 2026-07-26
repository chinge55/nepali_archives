"""Bind a task's capability tier to a concrete model for the driving tool.

The workflow graph records only *what kind of reader* a task needs
(``strong_reader`` / ``fast_reader``).  This module resolves that to a model
name and reasoning effort using ``ocr/agent_profiles.json``, so switching agent
CLIs is a config change and no vendor model ID is ever written into run state.

Resolution precedence, highest first:

1. a legacy explicit ``preferred_model`` stored on the task — runs created
   before capabilities existed keep routing exactly as they did;
2. the active profile's binding for the capability;
3. nothing — the tool uses its own default model, which is a valid outcome.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import settings


STRONG_READER = "strong_reader"
FAST_READER = "fast_reader"
CAPABILITIES = (STRONG_READER, FAST_READER)

# Task fields that only steer model routing.  They are deliberately excluded
# when comparing a stored task against a rebuilt one: Gate 1 approves page
# ranges, roles, and inputs — never which model reads them.  Excluding them is
# what lets a paused run resume under a different tool.
ROUTING_FIELDS = frozenset({"capability", "preferred_model", "reasoning_effort"})

DEFAULT_PROFILE = "default"


class ProfileError(ValueError):
    """A requested capability is not one this workflow defines."""


@dataclass(frozen=True)
class Routing:
    """How one task should be routed.  Pinning nothing is legitimate."""

    profile: str
    capability: str | None
    model: str | None = None
    reasoning_effort: str | None = None


def load_profiles(path: str | Path | None = None) -> dict[str, Any]:
    """Read the bindings file.  Missing or malformed means "pin nothing"."""
    file = Path(path) if path is not None else settings.agent_profiles_path
    if not file.is_file():
        return {}
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def active_profile_name(profiles: dict[str, Any] | None = None) -> str:
    """The profile set in force: env override, else the file's, else default."""
    if settings.agent_profile:
        return settings.agent_profile
    data = load_profiles() if profiles is None else profiles
    active = data.get("active")
    return active if isinstance(active, str) and active else DEFAULT_PROFILE


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def resolve(
    capability: str | None,
    *,
    preferred_model: str | None = None,
    reasoning_effort: str | None = None,
    profiles: dict[str, Any] | None = None,
) -> Routing:
    """Resolve one task's routing.  See the module docstring for precedence."""
    data = load_profiles() if profiles is None else profiles
    name = active_profile_name(data)

    if preferred_model:
        return Routing(
            profile=name,
            capability=capability,
            model=preferred_model,
            reasoning_effort=reasoning_effort,
        )
    if capability is None:
        return Routing(profile=name, capability=None)
    if capability not in CAPABILITIES:
        raise ProfileError(
            f"unknown capability {capability!r}; expected one of {list(CAPABILITIES)}"
        )

    table = data.get("profiles")
    binding = table.get(name) if isinstance(table, dict) else None
    entry = binding.get(capability) if isinstance(binding, dict) else None
    if not isinstance(entry, dict):
        return Routing(profile=name, capability=capability)
    return Routing(
        profile=name,
        capability=capability,
        model=_text(entry.get("model")),
        reasoning_effort=_text(entry.get("reasoning_effort")),
    )


__all__ = [
    "CAPABILITIES",
    "DEFAULT_PROFILE",
    "FAST_READER",
    "ProfileError",
    "ROUTING_FIELDS",
    "Routing",
    "STRONG_READER",
    "active_profile_name",
    "load_profiles",
    "resolve",
]
