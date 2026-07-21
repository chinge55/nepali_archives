#!/usr/bin/env python3
"""rashifal.py — the per-राशि daily state machine (Stage 2).

Everything here is computed from classical, public-domain rules
(horoscope/rules.md). The per-राशि day quality derives from:

  1. चन्द्र गोचर house — today's Moon counted from each राशि.
     Favorable in 1,3,6,7,10,11; the 8th is चन्द्राष्टम (फलदीपिका अ.२६).
  2. तिथि class — नन्दा/भद्रा/जया/रिक्ता/पूर्णा pentads; रिक्ता cautioned.
  3. योग class — the nine classically inauspicious yogas.

The prose is a TEMPLATE POOL in the measured register (reviews/04 §4),
selected deterministically by (date, राशि) so builds are reproducible.
Templates are house prose, clearly labelled मनोरञ्जन on the page — the
computed facts above are the citable part. [Nepali template text pending
native-speaker review — flagged in plan.md Stage 2.]
"""
from __future__ import annotations

import datetime as dt
import hashlib

from panchanga import RASHI, compute

# फलदीपिका अ.२६: favorable houses for the transiting Moon from the राशि
FAVORABLE_HOUSES = {1, 3, 6, 7, 10, 11}
CHANDRASHTAMA_HOUSE = 8

# tithi pentads (1-based index within the 15-tithi paksha cycle)
TITHI_CLASS = ["नन्दा", "भद्रा", "जया", "रिक्ता", "पूर्णा"]  # idx % 5
INAUSPICIOUS_YOGAS = {"विष्कम्भ", "अतिगण्ड", "शूल", "गण्ड", "व्याघात",
                      "वज्र", "व्यतीपात", "परिघ", "वैधृति"}

# नामाक्षर table (reviews/01 §2) — how readers find their राशि
NAMAKSHAR = {
    "मेष": "चू चे चो ला ली लू ले लो अ",
    "वृष": "ई ऊ ए ओ बा बी बू बे बो",
    "मिथुन": "का की कू घ ङ छ के को हा",
    "कर्कट": "ही हू हे हो डा डी डु डे डो",
    "सिंह": "मा मी मू मे मो टा टी टू टे",
    "कन्या": "टो पा पी पू ष ण ठ पे पो",
    "तुला": "रा री रू रे रो ता ती तू ते",
    "वृश्चिक": "तो ना नी नू ने नो या यी यू",
    "धनु": "ये यो भा भी भू धा फा ढा भे",
    "मकर": "भो जा जी खी खू खे खो गा गी",
    "कुम्भ": "गू गे गो सा सी सू से सो दा",
    "मीन": "दी दू थ झ ञ दे दो चा ची",
}

# ---- template pools (मनोरञ्जन; register per reviews/04 §4) ------------------
# {valence: {slot: [variants]}} — soft potential mood, one hedged caution.

T = {
    "शुभ": {
        "opening": [
            "आजको दिन तपाईंका लागि अनुकूल रहनेछ।",
            "सोचेका काम बन्दै जाने दिन छ।",
            "मनमा उत्साह र आत्मविश्वास बढ्नेछ।",
            "अड्किएका काम अघि बढ्ने सम्भावना छ।",
            "बिहानैदेखि वातावरण सहज र मन हलुका रहनेछ।",
        ],
        "domains": {
            "काम": [
                "कामकाजमा सहकर्मीको साथ पाइनेछ र जिम्मेवारी सहजै पूरा हुनेछ।",
                "व्यवसायमा नयाँ अवसर देखिन सक्छ, अघि बढ्न नहिचकिचाउनुहोस्।",
                "माथिल्लो तहबाट तपाईंको कामको कदर हुने योग छ।",
            ],
            "धन": [
                "आम्दानीका नयाँ बाटा देखिन सक्छन्।",
                "रोकिएको रकम प्राप्त हुने वा लेनदेन मिल्ने सम्भावना छ।",
                "लगानीका लागि सोचिरहनुभएको छ भने सल्लाह लिएर अघि बढ्नुहोस्।",
            ],
            "परिवार": [
                "परिवारजनसँगको समय सुखद रहनेछ।",
                "घरमा शुभ समाचार आउन सक्छ, वातावरण रमाइलो हुनेछ।",
                "आफन्तसँगको भेटघाटले मन प्रफुल्ल बनाउनेछ।",
            ],
            "स्वास्थ्य": [
                "स्वास्थ्यमा स्फूर्ति महसुस हुनेछ।",
                "शरीरमा ऊर्जा रहनेछ, नियमित व्यायामले थप लाभ दिनेछ।",
            ],
            "शिक्षा": [
                "अध्ययन र सिकाइमा प्रगति हुनेछ।",
                "विद्यार्थीका लागि परीक्षा वा नतिजामा राम्रो योग छ।",
                "नयाँ सीप सिक्न थाल्नुभएको छ भने त्यसले फल दिन थाल्नेछ।",
            ],
        },
        "caveat": [
            "तर हतारमा गरिएको निर्णयले भने काम बिगार्न सक्छ।",
            "तर आफ्नो कुरा सबैतिर नखोल्दा नै राम्रो हुनेछ।",
            "तर खर्चको हिसाब भने राखिरहनुहोस्।",
        ],
        "advice": [
            "नयाँ काम थाल्न आजको दिन उपयुक्त छ।",
            "भेटघाट र सम्पर्क बढाउनुहोस्, लाभ होला।",
            "योजना बनाएर अघि बढ्नुहोस्, दिनको साथ रहनेछ।",
            "आफ्नो अनुभव अरूसँग बाँड्नुहोस्, सम्मान बढ्नेछ।",
        ],
    },
    "मध्यम": {
        "opening": [
            "दिन मिश्रित फलदायी रहनेछ।",
            "काममा धैर्य चाहिने दिन छ।",
            "अपेक्षा र उपलब्धिबीच केही फरक पर्न सक्छ।",
            "साना कुरामा समय खर्चिनुपर्ला।",
            "दिनको पहिलो र दोस्रो पहर फरक-फरक अनुभव दिन सक्छ।",
        ],
        "domains": {
            "काम": [
                "कामकाजमा सामान्य प्रगति हुनेछ, ठूलो फड्को भने नखोज्नुहोस्।",
                "पुराना काम सक्नेतिर ध्यान दिनुहोस्, नयाँ जिम्मेवारी पर्खन सक्छ।",
                "सहकर्मीसँग समन्वय राख्दा काम सहज बन्नेछ।",
            ],
            "धन": [
                "खर्च बढ्न सक्छ, हिसाब राख्नुहोस्।",
                "लेनदेनमा कागजी कुरा प्रस्ट राख्नुहोस्।",
                "अनावश्यक किनमेल टार्दा पछुताउनुपर्ने छैन।",
            ],
            "परिवार": [
                "परिवारमा सरसल्लाह उपयोगी होला।",
                "घरका जेठा सदस्यको कुरा सुन्दा बाटो देखिनेछ।",
                "सन्तानका विषयमा केही सोच-विचार गर्नुपर्ला।",
            ],
            "स्वास्थ्य": [
                "स्वास्थ्यमा सामान्य ख्याल पुर्‍याउनुहोस्।",
                "खानपान नियमित राख्दा दिन सहज रहनेछ।",
                "थकान महसुस भए आराम गर्न नहिचकिचाउनुहोस्।",
            ],
            "शिक्षा": [
                "अध्ययनमा एकाग्रता जुटाउन प्रयास चाहिनेछ।",
                "यात्राको योजना छ भने समय मिलाएर हिँड्नुहोस्।",
            ],
        },
        "caveat": [
            "तर अपरान्हतिर भने केही अलमल हुन सक्छ।",
            "तर अरूको भरमा मात्र काम नछोड्नुहोस्।",
            "तर सुनेका कुरामा तुरुन्तै विश्वास नगर्नुहोस्।",
        ],
        "advice": [
            "हतारमा निर्णय नगर्नुहोस्।",
            "आजको काम भोलि नसार्नुहोस्।",
            "कुराकानीमा नरमता राख्नुहोस्, काम बन्नेछ।",
            "धैर्य राख्नुहोस्, साँझतिर स्थिति खुल्नेछ।",
        ],
    },
    "सावधान": {
        "opening": [
            "आज जोगिएर काम गर्नुपर्ने दिन छ।",
            "मन केही भारी रहन सक्छ।",
            "योजनामा अवरोध आउन सक्छ।",
            "आवेगमा आएर निर्णय लिने दिन होइन।",
            "आजको दिन आफूलाई सम्हालेर चल्नुपर्ने देखिन्छ।",
        ],
        "domains": {
            "काम": [
                "कामकाजमा अनपेक्षित अड्चन आउन सक्छ, वैकल्पिक तयारी राख्नुहोस्।",
                "नयाँ सम्झौता वा ठूला निर्णय आजका लागि नटुङ्ग्याउनुहोस्।",
                "काममा आलोचना सुन्नुपर्ला, त्यसलाई सुझावका रूपमा लिनुहोस्।",
            ],
            "धन": [
                "ठूलो लगानी वा जोखिमपूर्ण काम टार्नुहोस्।",
                "ऋण लिने-दिने काम आज नगर्दा राम्रो।",
                "खल्तीमा भन्दा बढी खर्चको योजना नबनाउनुहोस्।",
            ],
            "परिवार": [
                "बोलीचालीमा संयम राख्दा घरको वातावरण शान्त रहनेछ।",
                "पुरानो कुरा उप्काएर विवाद नबढाउनुहोस्।",
            ],
            "स्वास्थ्य": [
                "खानपानमा ख्याल नगर्दा स्वास्थ्यमा असर पर्ला।",
                "आराम र निद्रालाई प्राथमिकता दिनुहोस्।",
                "पेट वा टाउकोसम्बन्धी सानो समस्याले सताउन सक्छ, बेवास्ता नगर्नुहोस्।",
            ],
            "शिक्षा": [
                "यात्रामा सतर्कता अपनाउनुहोस्, सामान ख्याल गर्नुहोस्।",
                "महत्त्वपूर्ण कागजपत्र सम्हालेर राख्नुहोस्।",
            ],
        },
        "caveat": [
            "तर साँझपख भने स्थिति क्रमशः सहज बन्दै जानेछ।",
            "तर मित्रको साथले दिनलाई हलुका बनाउनेछ।",
            "तर धैर्य राखे यो समय पनि टर्नेछ।",
        ],
        "advice": [
            "आजको दिन धैर्यले काट्नुहोस्, भोलि सहज हुनेछ।",
            "पुराना मित्रको सल्लाह काम लाग्नेछ।",
            "ठूला निर्णय एक-दुई दिन पर सार्नुहोस्।",
            "आफ्नै काममा ध्यान दिनुहोस्, अरूको कुराले नछुनुहोस्।",
        ],
    },
}

def _pick(pool: list[str], seed: str, salt: str) -> str:
    digest = hashlib.sha256(f"{seed}:{salt}".encode()).digest()
    return pool[digest[0] % len(pool)]


def day_state(date: dt.date) -> dict:
    """The computed layer for one date + the 12 per-राशि readings."""
    p = compute(date)
    tithi_idx = p["tithi"].index % 15          # position within the paksha
    tithi_class = TITHI_CLASS[tithi_idx % 5]
    yoga_bad = p["yoga"].name in INAUSPICIOUS_YOGAS
    moon_idx = p["moon_rashi"].index

    rashis = []
    for i, name in enumerate(RASHI):
        house = ((moon_idx - i) % 12) + 1      # Moon counted from this राशि
        chandrashtama = house == CHANDRASHTAMA_HOUSE
        score = (2 if house in FAVORABLE_HOUSES else -1) \
            + (-3 if chandrashtama else 0) \
            + (-1 if tithi_class == "रिक्ता" else 0) \
            + (-1 if yoga_bad else 0)
        valence = "शुभ" if score >= 2 else ("सावधान" if score <= -2 else "मध्यम")

        seed = f"{date.isoformat()}:{name}"
        pools = T[valence]
        cats = sorted(pools["domains"])
        d1 = _pick(cats, seed, "c1")
        d2 = _pick([c for c in cats if c != d1], seed, "c2")
        text = " ".join((
            _pick(pools["opening"], seed, "o"),
            _pick(pools["domains"][d1], seed, "d1"),
            _pick(pools["domains"][d2], seed, "d2"),
            _pick(pools["caveat"], seed, "cv"),
            _pick(pools["advice"], seed, "a"),
        ))
        rule = (f"चन्द्रमा {name}बाट {house}औँ स्थानमा — "
                + ("चन्द्राष्टम" if chandrashtama else
                   ("शुभ स्थान" if house in FAVORABLE_HOUSES else "सामान्य स्थान"))
                + " (फलदीपिका, अध्याय २६)")
        rashis.append(dict(rashi=name, namakshar=NAMAKSHAR[name], house=house,
                           chandrashtama=chandrashtama, valence=valence,
                           text=text, rule=rule))

    return dict(panchanga=p, tithi_class=tithi_class, yoga_bad=yoga_bad,
                chandrashtama_rashi=RASHI[(moon_idx - 7) % 12], rashis=rashis)


if __name__ == "__main__":
    import sys
    date = (dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1
            else dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=45))).date())
    s = day_state(date)
    p = s["panchanga"]
    print(f"{p['bs_str']} · तिथि {p['tithi'].name} ({s['tithi_class']}) · "
          f"योग {p['yoga'].name}{' (अशुभ)' if s['yoga_bad'] else ''} · "
          f"चन्द्राष्टम: {s['chandrashtama_rashi']}")
    for r in s["rashis"]:
        flag = " ⚠चन्द्राष्टम" if r["chandrashtama"] else ""
        print(f"\n{r['rashi']} ({r['valence']}{flag}) — {r['rule']}")
        print(f"  {r['text']}")
