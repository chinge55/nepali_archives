#!/usr/bin/env python3
"""Regression fixture for the panchanga engine, frozen against
drikpanchang.com (Kathmandu, geoname 1283240), fetched 2026-07-21.

Asserts: anga NAMES exact; end times within TOLERANCE_MIN; sunrise within
2 min; BS dates exact. Names are the hard contract — a name mismatch means
a real bug (wrong sector/ayanamsa/sunrise), never tolerance noise.

Observed deltas at freeze time: tithi/karana (ayanamsa-invariant) 0-1 min;
nakshatra/yoga/rashi 2-5 min (our True-Chitra vs theirs differs by ~1-2
arc-min — tuning item, see plan.md Stage 1 notes).

Run: ~/miniconda3/envs/patro_env/bin/python validate_panchanga.py
"""
import datetime as dt
import sys

from panchanga import compute

TOLERANCE_MIN = 6

# date -> expected (from drikpanchang; end times NPT, +1 = next civil day)
FIXTURE = {
    "2026-07-21": {
        "bs": "२०८३-०४-०५", "vara": "मङ्गलबार", "sunrise": "05:21",
        "tithi": ("शुक्ल अष्टमी", "05:33+1"),
        "nakshatra": ("चित्रा", "21:04"),
        "yoga": ("सिद्ध", "18:40"),
        "karana": ("विष्टि", "16:49"),
        "moon_rashi": ("कन्या", "08:09"),
    },
    "2026-01-01": {
        "bs": "२०८२-०९-१७", "vara": "बिहीबार", "sunrise": "06:55",
        "tithi": ("शुक्ल त्रयोदशी", "22:37"),
        "nakshatra": ("रोहिणी", "23:03"),
        "yoga": ("शुभ", "17:27"),
        "karana": ("कौलव", "12:20"),
        "moon_rashi": ("वृष", None),   # drik showed nakshatra end, not rashi end
    },
    "2026-10-20": {
        "bs": "२०८३-०७-०३", "vara": "मङ्गलबार", "sunrise": "06:07",
        "tithi": ("शुक्ल नवमी", "13:05"),
        "nakshatra": ("श्रवण", "18:17"),
        "yoga": ("शूल", "01:05+1"),
        "karana": ("कौलव", "13:05"),
        "moon_rashi": ("मकर", None),      # drik shows pada transition, not rashi end
    },
}


def _minutes(hhmm: str) -> int:
    plus = hhmm.endswith("+1")
    if plus:
        hhmm = hhmm[:-2]          # NOT rstrip("+1") — that eats trailing 1s
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m) + (1440 if plus else 0)


def main() -> None:
    bad = []
    for iso, want in FIXTURE.items():
        date = dt.date.fromisoformat(iso)
        got = compute(date)
        if got["bs"] != want["bs"]:
            bad.append(f"{iso}: BS {got['bs']} != {want['bs']}")
        if got["vara"] != want["vara"]:
            bad.append(f"{iso}: vara {got['vara']} != {want['vara']}")
        if abs(_minutes(got["sunrise"]) - _minutes(want["sunrise"])) > 2:
            bad.append(f"{iso}: sunrise {got['sunrise']} vs {want['sunrise']}")
        for key in ("tithi", "nakshatra", "yoga", "karana", "moon_rashi"):
            name, end = want[key]
            anga = got[key]
            if anga.name != name:
                bad.append(f"{iso}: {key} NAME {anga.name!r} != {name!r}")
                continue
            if end is None:
                continue
            got_end = anga.ends.strftime("%H:%M") + (
                "+1" if anga.ends.date() != date else "")
            if abs(_minutes(got_end) - _minutes(end)) > TOLERANCE_MIN:
                bad.append(f"{iso}: {key} end {got_end} vs {end} (>±{TOLERANCE_MIN}m)")
    if bad:
        print("FAIL")
        for b in bad:
            print(" ", b)
        sys.exit(1)
    print(f"OK: {len(FIXTURE)} dates × 5 angas + BS/vara/sunrise match "
          f"drikpanchang within ±{TOLERANCE_MIN} min (names exact)")


if __name__ == "__main__":
    main()
