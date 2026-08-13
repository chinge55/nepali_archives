#!/usr/bin/env python3
"""panchanga.py — the computed layer: Kathmandu panchanga for any date.

Clean-license stack (horoscope/rules.md): Skyfield (MIT) + JPL DE440s
(positional facts) + this ~200-line anga layer we own + nepali-datetime
(Apache-2.0). No AGPL anywhere.

Conventions (literature_review.md §4):
- Angas (तिथि, नक्षत्र, योग, करण) are reported as prevailing at KATHMANDU
  SUNRISE, with their end times — matching drikpanchang's presentation.
- Sidereal longitudes use the True Chitra Paksha ayanamsa (Spica at 180°),
  computed from Skyfield itself; `--ayanamsa lahiri` selects the linear
  Lahiri approximation for comparison.
- BS dates via nepali-datetime (table-based, BS 1975-2100).

Usage:
    python panchanga.py                # today (NPT)
    python panchanga.py 2026-07-21
    python panchanga.py 2026-07-21 --ayanamsa lahiri
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import nepali_datetime
from skyfield import almanac
from skyfield.api import Loader, Star, wgs84

NPT = ZoneInfo("Asia/Kathmandu")
KATHMANDU = dict(latitude_degrees=27.7172, longitude_degrees=85.3240,
                 elevation_m=1400)

# Spica / चित्रा (HIP 65474), ICRS J1991.25 catalog values (Hipparcos):
# the True Chitra Paksha ayanamsa is DEFINED by Spica sitting at sidereal 180°.
SPICA = Star(ra_hours=(13, 25, 11.579), dec_degrees=(-11, 9, 40.75),
             ra_mas_per_year=-42.35, dec_mas_per_year=-30.67,
             parallax_mas=13.06, radial_km_per_s=1.0)

TITHI = ["प्रतिपदा", "द्वितीया", "तृतीया", "चतुर्थी", "पञ्चमी", "षष्ठी",
         "सप्तमी", "अष्टमी", "नवमी", "दशमी", "एकादशी", "द्वादशी",
         "त्रयोदशी", "चतुर्दशी"]
NAKSHATRA = ["अश्विनी", "भरणी", "कृत्तिका", "रोहिणी", "मृगशिरा", "आर्द्रा",
             "पुनर्वसु", "पुष्य", "आश्लेषा", "मघा", "पूर्वाफाल्गुनी",
             "उत्तराफाल्गुनी", "हस्त", "चित्रा", "स्वाती", "विशाखा", "अनुराधा",
             "ज्येष्ठा", "मूल", "पूर्वाषाढा", "उत्तराषाढा", "श्रवण", "धनिष्ठा",
             "शतभिषा", "पूर्वभाद्रपदा", "उत्तरभाद्रपदा", "रेवती"]
YOGA = ["विष्कम्भ", "प्रीति", "आयुष्मान्", "सौभाग्य", "शोभन", "अतिगण्ड",
        "सुकर्मा", "धृति", "शूल", "गण्ड", "वृद्धि", "ध्रुव", "व्याघात",
        "हर्षण", "वज्र", "सिद्धि", "व्यतीपात", "वरीयान्", "परिघ", "शिव",
        "सिद्ध", "साध्य", "शुभ", "शुक्ल", "ब्रह्म", "इन्द्र", "वैधृति"]
KARANA_MOVABLE = ["बव", "बालव", "कौलव", "तैतिल", "गर", "वणिज", "विष्टि"]
RASHI = ["मेष", "वृष", "मिथुन", "कर्कट", "सिंह", "कन्या", "तुला", "वृश्चिक",
         "धनु", "मकर", "कुम्भ", "मीन"]
VARA = ["आइतबार", "सोमबार", "मङ्गलबार", "बुधबार", "बिहीबार", "शुक्रबार",
        "शनिबार"]  # index = weekday with Sunday=0


@lru_cache(maxsize=1)
def _sky():
    """Ephemeris + timescale, cached in a portable user-cache location."""
    cache_root = Path(
        os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    ).expanduser()
    data_dir = Path(
        os.environ.get(
            "SKYFIELD_DATA", str(cache_root / "nepali-archives" / "skyfield")
        )
    ).expanduser()
    load = Loader(str(data_dir), verbose=False)
    eph = load("de440s.bsp")
    return load.timescale(), eph


def _ecliptic_lon(t, body_name: str) -> float:
    """Apparent geocentric ecliptic longitude of date, degrees."""
    ts, eph = _sky()
    body = SPICA if body_name == "spica" else eph[body_name]
    astrometric = eph["earth"].at(t).observe(body).apparent()
    _, lon, _ = astrometric.frame_latlon(_ecliptic_frame())
    return lon.degrees % 360.0


@lru_cache(maxsize=1)
def _ecliptic_frame():
    from skyfield.framelib import ecliptic_frame
    return ecliptic_frame


def ayanamsa(t, kind: str = "chitra") -> float:
    """Degrees to subtract from tropical to get sidereal longitude."""
    if kind == "chitra":          # True Chitra Paksha: Spica defined at 180°
        return (_ecliptic_lon(t, "spica") - 180.0) % 360.0
    if kind == "lahiri":          # linear approximation, J2000 anchor
        years = (t.tt - 2451545.0) / 365.25
        return 23.853222 + years * (50.2888 / 3600.0)
    raise ValueError(kind)


def sunrise(date: dt.date):
    """Kathmandu sunrise for the civil date, as a Skyfield time."""
    ts, eph = _sky()
    place = wgs84.latlon(**KATHMANDU)
    t0 = ts.from_datetime(dt.datetime.combine(date, dt.time(0, 0), NPT))
    t1 = ts.from_datetime(dt.datetime.combine(date, dt.time(23, 59), NPT))
    times, events = almanac.find_risings(eph["earth"] + place, eph["sun"], t0, t1)
    if not len(times):
        raise RuntimeError(f"no sunrise found for {date}")
    return times[0]


# ---- the five limbs --------------------------------------------------------

@dataclass
class Anga:
    name: str
    index: int           # 0-based within its cycle
    ends: dt.datetime    # NPT time this anga ends


def _angle(t, kind: str, ayan: str) -> float:
    """The rotating angle whose sector defines each anga, degrees."""
    moon = _ecliptic_lon(t, "moon")
    sun = _ecliptic_lon(t, "sun")
    if kind == "tithi":
        return (moon - sun) % 360.0                     # ayanamsa-invariant
    if kind == "yoga":
        a = ayanamsa(t, ayan)
        return ((moon - a) + (sun - a)) % 360.0
    if kind == "nakshatra":
        return (moon - ayanamsa(t, ayan)) % 360.0
    raise ValueError(kind)


def _find_end(t_start, kind: str, ayan: str, sector: float) -> dt.datetime:
    """When does the current anga (of width `sector`°) end? Bisection."""
    ts, _ = _sky()
    start_angle = _angle(t_start, kind, ayan)
    target = (int(start_angle // sector) + 1) * sector % 360.0

    def past(t) -> bool:
        return ((_angle(t, kind, ayan) - target) % 360.0) < 180.0

    lo, hi = 0.0, 0.05          # days; angas last < ~1.2 days
    while not past(ts.tt_jd(t_start.tt + hi)):
        lo, hi = hi, hi + 0.05
        if hi > 2.5:
            raise RuntimeError("anga end not found")
    for _ in range(40):
        mid = (lo + hi) / 2
        if past(ts.tt_jd(t_start.tt + mid)):
            hi = mid
        else:
            lo = mid
    end = ts.tt_jd(t_start.tt + hi)
    return end.astimezone(NPT).replace(tzinfo=None, microsecond=0)


def tithi(t, ayan: str) -> Anga:
    idx = int(_angle(t, "tithi", ayan) // 12.0)          # 0..29
    if idx == 14:
        name = "पूर्णिमा"
    elif idx == 29:
        name = "औंसी"
    else:
        name = TITHI[idx % 15]
    paksha = "शुक्ल" if idx < 15 else "कृष्ण"
    return Anga(f"{paksha} {name}", idx, _find_end(t, "tithi", ayan, 12.0))


def nakshatra(t, ayan: str) -> Anga:
    width = 360.0 / 27.0
    idx = int(_angle(t, "nakshatra", ayan) // width)
    return Anga(NAKSHATRA[idx], idx, _find_end(t, "nakshatra", ayan, width))


def yoga(t, ayan: str) -> Anga:
    width = 360.0 / 27.0
    idx = int(_angle(t, "yoga", ayan) // width)
    return Anga(YOGA[idx], idx, _find_end(t, "yoga", ayan, width))


def karana(t, ayan: str) -> Anga:
    half = int(_angle(t, "tithi", ayan) // 6.0)          # 0..59
    if half == 0:
        name = "किंस्तुघ्न"
    elif half >= 57:
        name = ["शकुनि", "चतुष्पाद", "नाग"][half - 57]
    else:
        name = KARANA_MOVABLE[(half - 1) % 7]
    return Anga(name, half, _find_end(t, "tithi", ayan, 6.0))


def moon_rashi(t, ayan: str) -> Anga:
    idx = int(_angle(t, "nakshatra", ayan) // 30.0)
    return Anga(RASHI[idx], idx, _find_end(t, "nakshatra", ayan, 30.0))


# ---- the day ----------------------------------------------------------------

def compute(date: dt.date, ayan: str = "chitra") -> dict:
    t = sunrise(date)
    rise_npt = t.astimezone(NPT)
    ts, eph = _sky()
    place = wgs84.latlon(**KATHMANDU)
    t0 = ts.from_datetime(dt.datetime.combine(date, dt.time(0, 0), NPT))
    t1 = ts.from_datetime(dt.datetime.combine(date, dt.time(23, 59), NPT))
    sets, _ = almanac.find_settings(eph["earth"] + place, eph["sun"], t0, t1)
    bs = nepali_datetime.date.from_datetime_date(date)
    return {
        "ad": date.isoformat(),
        "bs": bs.strftime("%K-%n-%D"),
        "bs_str": bs.strftime("%N %D गते"),
        "vara": VARA[(date.weekday() + 1) % 7],
        "sunrise": rise_npt.strftime("%H:%M"),
        "sunset": sets[0].astimezone(NPT).strftime("%H:%M") if len(sets) else "",
        "tithi": tithi(t, ayan),
        "nakshatra": nakshatra(t, ayan),
        "yoga": yoga(t, ayan),
        "karana": karana(t, ayan),
        "moon_rashi": moon_rashi(t, ayan),
        "ayanamsa_deg": round(ayanamsa(t, ayan), 4),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("date", nargs="?", default=None, help="YYYY-MM-DD (AD)")
    p.add_argument("--ayanamsa", choices=("chitra", "lahiri"), default="chitra")
    args = p.parse_args()
    date = (dt.date.fromisoformat(args.date) if args.date
            else dt.datetime.now(NPT).date())
    d = compute(date, args.ayanamsa)
    print(f"मिति: {d['bs_str']} ({d['bs']} वि.सं.) · {d['ad']} · {d['vara']}")
    print(f"सूर्योदय {d['sunrise']} · सूर्यास्त {d['sunset']} (काठमाडौं)")
    for key, label in (("tithi", "तिथि"), ("nakshatra", "नक्षत्र"),
                       ("yoga", "योग"), ("karana", "करण"),
                       ("moon_rashi", "चन्द्र राशि")):
        a = d[key]
        when = a.ends.strftime("%H:%M")
        if a.ends.date() != date:                      # ends after midnight
            when = f"राति {when} (भोलिपल्ट)"
        print(f"{label}: {a.name}  (समाप्ति {when})")
    print(f"[ayanamsa {d['ayanamsa_deg']}°]")


if __name__ == "__main__":
    main()
