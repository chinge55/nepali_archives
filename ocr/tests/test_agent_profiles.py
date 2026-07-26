#!/usr/bin/env python3
"""Plain-assert spec for capability -> model resolution.

The graph must never carry a vendor model ID; this module is the only place a
capability becomes a concrete model, so its precedence rules are load-bearing.
"""
import json
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from archive_ocr import agent_profiles
from archive_ocr.agent_profiles import (
    CAPABILITIES,
    DEFAULT_PROFILE,
    FAST_READER,
    STRONG_READER,
    ProfileError,
    ROUTING_FIELDS,
    active_profile_name,
    load_profiles,
    resolve,
)


PROFILES = {
    "active": "vendor-a",
    "profiles": {
        "vendor-a": {
            "strong_reader": {"model": "a-strong", "reasoning_effort": "high"},
            "fast_reader": {"model": "a-fast", "reasoning_effort": "medium"},
        },
        "vendor-b": {
            "strong_reader": {"model": "b-strong", "reasoning_effort": "high"},
            "fast_reader": {},
        },
        DEFAULT_PROFILE: {"strong_reader": {}, "fast_reader": {}},
    },
}


@contextmanager
def expect(exception):
    try:
        yield
    except exception:
        return
    raise AssertionError(f"expected {exception.__name__}")


@contextmanager
def profile_override(name: str):
    """Point settings.agent_profile at one profile set for the duration.

    Passing "" clears the override, which is how this spec stays hermetic no
    matter what OCR_AGENT_PROFILE the operator has exported.
    """
    previous = agent_profiles.settings.agent_profile
    object.__setattr__(agent_profiles.settings, "agent_profile", name)
    try:
        yield
    finally:
        object.__setattr__(agent_profiles.settings, "agent_profile", previous)


def test_active_profile_prefers_env_override_then_file() -> None:
    assert active_profile_name(PROFILES) == "vendor-a"
    with profile_override("vendor-b"):
        assert active_profile_name(PROFILES) == "vendor-b"
    # A file with no "active" key falls back to the neutral default.
    assert active_profile_name({}) == DEFAULT_PROFILE


def test_capability_resolves_through_the_active_profile() -> None:
    strong = resolve(STRONG_READER, profiles=PROFILES)
    assert (strong.profile, strong.model, strong.reasoning_effort) == (
        "vendor-a", "a-strong", "high",
    )
    with profile_override("vendor-b"):
        assert resolve(STRONG_READER, profiles=PROFILES).model == "b-strong"
        # vendor-b deliberately pins nothing for fast_reader.
        empty = resolve(FAST_READER, profiles=PROFILES)
        assert empty.model is None and empty.reasoning_effort is None
        assert empty.capability == FAST_READER


def test_legacy_preferred_model_wins_over_the_profile() -> None:
    routed = resolve(
        STRONG_READER,
        preferred_model="legacy-pin",
        reasoning_effort="high",
        profiles=PROFILES,
    )
    assert routed.model == "legacy-pin"
    assert routed.reasoning_effort == "high"
    # Still reports which profile set was in force, for the packet.
    assert routed.profile == "vendor-a"


def test_missing_capability_and_missing_bindings_pin_nothing() -> None:
    coordinator = resolve(None, profiles=PROFILES)
    assert coordinator.model is None and coordinator.capability is None
    unknown_profile = resolve(STRONG_READER, profiles={"active": "nope"})
    assert unknown_profile.model is None
    assert resolve(STRONG_READER, profiles={}).model is None


def test_unknown_capability_is_an_error_not_a_silent_default() -> None:
    with expect(ProfileError):
        resolve("wishful_reader", profiles=PROFILES)
    with expect(ProfileError):
        resolve("STRONG_READER", profiles=PROFILES)


def test_malformed_or_absent_file_degrades_instead_of_crashing() -> None:
    with tempfile.TemporaryDirectory(prefix="agent-profiles-") as temp:
        root = Path(temp)
        assert load_profiles(root / "does-not-exist.json") == {}
        broken = root / "broken.json"
        broken.write_text("{not json", encoding="utf-8")
        assert load_profiles(broken) == {}
        listy = root / "listy.json"
        listy.write_text("[1, 2]", encoding="utf-8")
        assert load_profiles(listy) == {}


def test_shipped_bindings_cover_every_capability() -> None:
    shipped = load_profiles(Path(__file__).resolve().parent.parent / "agent_profiles.json")
    assert shipped, "ocr/agent_profiles.json must be present and readable"
    active = shipped["active"]
    assert active in shipped["profiles"], f"active profile {active!r} is not defined"
    for name, bindings in shipped["profiles"].items():
        missing = set(CAPABILITIES) - set(bindings)
        assert not missing, f"profile {name!r} is missing {sorted(missing)}"


def test_routing_fields_match_the_task_model() -> None:
    from archive_ocr.book_workflow import Task

    fields = set(Task.model_fields)
    assert ROUTING_FIELDS <= fields, "ROUTING_FIELDS names a field Task lacks"
    # Excluding routing must still leave the archival shape intact.
    assert {"role", "inputs", "summary", "id", "node_id"} <= fields - ROUTING_FIELDS


if __name__ == "__main__":
    # Neutralize any ambient OCR_AGENT_PROFILE so the spec is deterministic;
    # the tests that care about overrides set them explicitly.
    with profile_override(""):
        test_active_profile_prefers_env_override_then_file()
        test_capability_resolves_through_the_active_profile()
        test_legacy_preferred_model_wins_over_the_profile()
        test_missing_capability_and_missing_bindings_pin_nothing()
        test_unknown_capability_is_an_error_not_a_silent_default()
        test_malformed_or_absent_file_degrades_instead_of_crashing()
        test_shipped_bindings_cover_every_capability()
        test_routing_fields_match_the_task_model()
    print("OK: agent_profiles.py resolution spec passes")
