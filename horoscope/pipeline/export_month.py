#!/usr/bin/env python3
"""export_month.py — freeze computed panchanga + rashifal state to JSON.

Writes horoscope/content/panchanga-YYYY-MM.json: per date, everything the
site renderer needs (panchanga angas with end times, per-राशि house/valence/
चन्द्राष्टम/rule/template-text). Pure computation — deterministic and
regenerable — committed as dated source so CI's build_site.py can render
/patro/ with stdlib only (no skyfield, no ephemeris, no API).

Run: ~/miniconda3/envs/patro_env/bin/python export_month.py --month YYYY-MM
     ... export_month.py [YYYY-MM-DD] [--days N]
"""
from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from rashifal import day_state

CONTENT = Path(__file__).resolve().parent.parent / "content"
NPT = ZoneInfo("Asia/Kathmandu")


def _anga(a) -> dict:
    return {"name": a.name, "ends": a.ends.isoformat(timespec="minutes")}


def export_day(date: dt.date) -> dict:
    s = day_state(date)
    p = s["panchanga"]
    return {
        "bs": p["bs"], "bs_str": p["bs_str"], "vara": p["vara"], "ad": p["ad"],
        "sunrise": p["sunrise"], "sunset": p["sunset"],
        "tithi": _anga(p["tithi"]), "nakshatra": _anga(p["nakshatra"]),
        "yoga": _anga(p["yoga"]), "karana": _anga(p["karana"]),
        "moon_rashi": _anga(p["moon_rashi"]),
        "tithi_class": s["tithi_class"],
        "chandrashtama_rashi": s["chandrashtama_rashi"],
        "rashis": [{"rashi": r["rashi"], "namakshar": r["namakshar"],
                    "house": r["house"], "valence": r["valence"],
                    "chandrashtama": r["chandrashtama"], "rule": r["rule"],
                    "text": r["text"]} for r in s["rashis"]],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("start", nargs="?", help="YYYY-MM-DD (default: today NPT)")
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--month", help="YYYY-MM — export the whole AD month")
    args = ap.parse_args()

    if args.month:
        y, m = map(int, args.month.split("-"))
        first = dt.date(y, m, 1)
        dates = [first + dt.timedelta(d) for d in range(calendar.monthrange(y, m)[1])]
    else:
        start = (dt.date.fromisoformat(args.start) if args.start
                 else dt.datetime.now(NPT).date())
        dates = [start + dt.timedelta(d) for d in range(args.days)]

    CONTENT.mkdir(exist_ok=True)
    by_month: dict[str, dict] = {}
    for date in dates:
        month = date.strftime("%Y-%m")
        if month not in by_month:
            path = CONTENT / f"panchanga-{month}.json"
            by_month[month] = (json.loads(path.read_text()) if path.exists()
                               else {"days": {}})
        by_month[month]["days"][date.isoformat()] = export_day(date)
        print(date, flush=True)

    for month, data in by_month.items():
        path = CONTENT / f"panchanga-{month}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
        print(f"wrote {path} ({len(data['days'])} days)")


if __name__ == "__main__":
    main()
