#!/usr/bin/env python3
"""Ensure the committed calendar includes today; warn before coverage runs out."""

import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def coverage(content, today):
    days = set()
    for path in sorted(Path(content).glob("panchanga-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))["days"]
        for key, record in data.items():
            date.fromisoformat(key)
            if record["ad"] != key:
                raise ValueError(f"calendar date mismatch: {path.name}: {key}")
        days.update(data)
    if today.isoformat() not in days:
        return None
    end = today
    while (end + timedelta(days=1)).isoformat() in days:
        end += timedelta(days=1)
    return end


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", type=Path, default=ROOT / "horoscope" / "content")
    parser.add_argument("--date", type=date.fromisoformat)
    parser.add_argument("--warn-days", type=int, default=30)
    args = parser.parse_args()
    today = args.date or (datetime.now(timezone.utc) + timedelta(hours=5, minutes=45)).date()
    end = coverage(args.content, today)
    if end is None:
        print(f"::error::Calendar data is missing for {today}; refresh the committed panchanga before publishing.")
        return 1
    left = (end - today).days
    print(f"Calendar covers {today} through {end} ({left} days ahead).")
    if left < args.warn_days:
        print(f"::warning::Calendar coverage ends on {end}; extend the committed panchanga soon.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
