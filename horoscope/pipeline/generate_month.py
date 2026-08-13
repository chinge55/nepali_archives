#!/usr/bin/env python3
"""generate_month.py — offline agent batch writer for the rashifal prose layer.

Architecture (see plan.md / reviews/05): the rules engine (rashifal.py) stays
the authority on WHAT kind of day each राशि has; the agent only writes richer
prose grounded in those computed facts. Output is a dated JSON batch under
horoscope/content/ that gets REVIEWED and COMMITTED as source — the daily
build never calls an API. Any entry that fails the mechanical validator is
dropped, and the renderer falls back to the deterministic template text.

Public config: horoscope/generation.yaml — writer tier, prompt, and validator.
Private binding: horoscope/generation.local.yaml — endpoint and concrete model.
Key: horoscope/.env (gitignored) — raw key or an *_API_KEY=... line.

Run: ~/miniconda3/envs/patro_env/bin/python generate_month.py [YYYY-MM-DD] [--days N]
     ... generate_month.py --month YYYY-MM        # whole AD month
"""
from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
import re
import time
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from rashifal import day_state

HERE = Path(__file__).resolve().parent
CONTENT = HERE.parent / "content"
CONFIG = yaml.safe_load((HERE.parent / "generation.yaml").read_text())
NPT = ZoneInfo("Asia/Kathmandu")


def _execution_config() -> dict:
    """Read the ignored provider/model binding only when generation runs."""
    path = HERE.parent / "generation.local.yaml"
    if not path.is_file():
        raise SystemExit(
            "missing horoscope/generation.local.yaml; copy the tracked example"
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data.get("endpoint") or not data.get("model"):
        raise SystemExit("generation.local.yaml needs endpoint and model")
    return data


def _api_key() -> str:
    raw = (HERE.parent / ".env").read_text().strip()
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            name, value = line.split("=", 1)
            if name.strip().endswith("_API_KEY") and value.strip():
                return value.strip()
        elif line:
            return line
    raise SystemExit("no writer API key found in horoscope/.env")


def _facts_prompt(state: dict, date: dt.date) -> str:
    p = state["panchanga"]
    lines = [
        f"मिति: {p['bs_str']} ({p['bs']} वि.सं.), {p['vara']} · {date.isoformat()}",
        f"तिथि: {p['tithi'].name} (वर्ग {state['tithi_class']}) · नक्षत्र: {p['nakshatra'].name}"
        f" · योग: {p['yoga'].name} · चन्द्र राशि: {p['moon_rashi'].name}",
        f"चन्द्राष्टम: {state['chandrashtama_rashi']}",
        "",
        "प्रत्येक राशिका गणना-तथ्य (यसैमा आधारित लेख्नुहोस्):",
    ]
    for r in state["rashis"]:
        extra = " — चन्द्राष्टम" if r["chandrashtama"] else ""
        lines.append(f"- {r['rashi']}: चन्द्र गोचर {r['house']}औं घर, वर्ग {r['valence']}{extra}")
    return "\n".join(lines)


def _call(key: str, user: str) -> dict:
    req_cfg = CONFIG["request"]
    execution = _execution_config()
    body = json.dumps({
        "model": execution["model"],
        "messages": [{"role": "system", "content": CONFIG["system_prompt"]},
                     {"role": "user", "content": user}],
        "response_format": {"type": req_cfg["response_format"]},
    }).encode()
    req = urllib.request.Request(
        execution["endpoint"], data=body,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=req_cfg["timeout_seconds"]) as resp:
        out = json.load(resp)
    return json.loads(out["choices"][0]["message"]["content"])


# validator: pure mechanics — anything it can't prove clean is dropped
# (renderer falls back to the template engine for that राशि).
_ALLOWED = re.compile(r'^[ऀ-ॿ‌‍\s।,;:!?()\'"‘’“”\-–—]+$')  # ZWJ/ZWNJ are valid Devanagari
_ASCII_ALPHA = re.compile(r"[A-Za-z]")


def _valid(text: str) -> str | None:
    v = CONFIG["validator"]
    t = " ".join(text.split())
    if not (v["min_chars"] <= len(t) <= v["max_chars"]):
        return f"length {len(t)}"
    if _ASCII_ALPHA.search(t):
        return "latin letters"
    if not _ALLOWED.match(t):
        bad = sorted({c for c in t if not _ALLOWED.match(c)})
        return f"charset {bad[:5]}"
    if not t.endswith("।"):
        return "no final danda"
    if t.count("।") < v["min_sentences"]:
        return f"fewer than {v['min_sentences']} sentences"
    return None


def generate_day(key: str, date: dt.date) -> tuple[dict, list[str]]:
    state = day_state(date)
    rashis = [r["rashi"] for r in state["rashis"]]
    got = _call(key, _facts_prompt(state, date))
    texts, problems = {}, []
    for name in rashis:
        text = got.get(name)
        if not isinstance(text, str):
            problems.append(f"{name}: missing")
            continue
        err = _valid(text)
        if err:
            problems.append(f"{name}: {err}")
            continue
        texts[name] = " ".join(text.split())
    return texts, problems


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("start", nargs="?", help="YYYY-MM-DD (default: today NPT)")
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--month", help="YYYY-MM — generate the whole AD month")
    args = ap.parse_args()

    if args.month:
        y, m = map(int, args.month.split("-"))
        first = dt.date(y, m, 1)
        dates = [first + dt.timedelta(d) for d in range(calendar.monthrange(y, m)[1])]
    else:
        start = (dt.date.fromisoformat(args.start) if args.start
                 else dt.datetime.now(NPT).date())
        dates = [start + dt.timedelta(d) for d in range(args.days)]

    key = _api_key()
    CONTENT.mkdir(exist_ok=True)
    by_month: dict[str, dict] = {}
    for date in dates:
        month = date.strftime("%Y-%m")
        if month not in by_month:
            path = CONTENT / f"{month}.json"
            by_month[month] = (json.loads(path.read_text()) if path.exists()
                               else {"days": {}})
        texts, problems = generate_day(key, date)
        by_month[month]["days"][date.isoformat()] = texts
        status = f"{len(texts)}/12"
        if problems:
            status += "  DROPPED: " + "; ".join(problems)
        print(f"{date}  {status}", flush=True)
        time.sleep(CONFIG["request"]["sleep_between_calls"])

    for month, data in by_month.items():
        data.pop("model", None)
        data["writer_tier"] = CONFIG["writer_tier"]
        data["generated_at"] = dt.datetime.now(NPT).strftime("%Y-%m-%d %H:%M")
        path = CONTENT / f"{month}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
        print(f"wrote {path} ({len(data['days'])} days)")


if __name__ == "__main__":
    main()
