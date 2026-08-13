# Review 1: ज्योतिष domain & Nepali tradition (agent review, 2026-07-21)

## 1. What a दैनिक राशिफल actually is: चन्द्र राशि, not sun signs

The single most important fact for authenticity: **Nepali/Vedic राशिफल is keyed to the moon sign (चन्द्र राशि / जन्म राशि), not the Western sun sign.** A person's राशि is the zodiac sign the **Moon occupied at their birth** (determined from the birth नक्षत्र), and the daily prediction is essentially a **गोचर (transit) reading**: where the Moon (and other planets) sits *today* relative to that natal moon sign.

Rationale: the Moon (चन्द्र) governs *manas* — mind, emotion, the instinctive daily experience — and moves fastest (full circuit ~27 days, ~2.25–2.5 days per राशि), giving 12× the temporal resolution of the Sun. (Sources: [Jyothish AI](https://jyothishai.com/learn/articles/moon-sign-meaning-vedic), [DrikPanchang Rashiphal](https://www.drikpanchang.com/astrology/prediction/vedic-astrology-rashiphal.html), [AstroSight](https://astrosight.ai/planets/moon-sign-significance-vedic-astrology))

**UX consequence:** users find their राशि by **name-syllable (नामाक्षर)** or by birth data, NOT by birth month. A sun-sign picker would be the tell-tale mark of a generic product.

## 2. The 12 राशि and the नामाक्षर table

Each राशि spans 2¼ नक्षत्र (9 पादs = 9 syllables). Names traditionally begin with the syllable of the birth नक्षत्र-पाद, so a name's first letter maps to a राशि. Cross-verified ([Lokpath](https://www.lokpath.com/story/246652/), [Prem Kumar Sharma](https://articles.premastrologer.com/rashi-namakshar/)); Nepali forms (व→ब convention):

| # | राशि | Western | नक्षत्र span | नामाक्षर |
|---|---|---|---|---|
| 1 | मेष | Aries | अश्विनी, भरणी, कृत्तिका(१) | चू, चे, चो, ला, ली, लू, ले, लो, अ |
| 2 | वृष (वृषभ) | Taurus | कृत्तिका(३), रोहिणी, मृगशिरा(२) | ई, ऊ, ए, ओ, बा, बी, बू, बे, बो |
| 3 | मिथुन | Gemini | मृगशिरा(२), आर्द्रा, पुनर्वसु(३) | का, की, कू, घ, ङ, छ, के, को, हा |
| 4 | कर्कट | Cancer | पुनर्वसु(१), पुष्य, आश्लेषा | ही, हू, हे, हो, डा, डी, डु, डे, डो |
| 5 | सिंह | Leo | मघा, पूर्वाफाल्गुनी, उत्तराफाल्गुनी(१) | मा, मी, मू, मे, मो, टा, टी, टू, टे |
| 6 | कन्या | Virgo | उत्तराफाल्गुनी(३), हस्त, चित्रा(२) | टो, पा, पी, पू, ष, ण, ठ, पे, पो |
| 7 | तुला | Libra | चित्रा(२), स्वाती, विशाखा(३) | रा, री, रू, रे, रो, ता, ती, तू, ते |
| 8 | वृश्चिक | Scorpio | विशाखा(१), अनुराधा, ज्येष्ठा | तो, ना, नी, नू, ने, नो, या, यी, यू |
| 9 | धनु | Sagittarius | मूल, पूर्वाषाढा, उत्तराषाढा(१) | ये, यो, भा, भी, भू, धा, फा, ढा, भे |
| 10 | मकर | Capricorn | उत्तराषाढा(३), श्रवण, धनिष्ठा(२) | भो, जा, जी, खी, खू, खे, खो, गा, गी |
| 11 | कुम्भ | Aquarius | धनिष्ठा(२), शतभिषा, पूर्वभाद्रपदा(३) | गू, गे, गो, सा, सी, सू, से, सो, दा |
| 12 | मीन | Pisces | पूर्वभाद्रपदा(१), उत्तरभाद्रपदा, रेवती | दी, दू, थ, झ, ञ, दे, दो, चा, ची |

Caveat: minor spelling variants across sources (कन्या ठ vs ढ). Syllables are pronunciation-initials — map both vowel-sign and bare-consonant forms.

## 3. गोचर (transit) rules — the citable rule tables

### 3a. Moon transit from natal Moon (the core daily engine)

Classical rule (बृहत्संहिता + फलदीपिका agree): counting the Moon's current sign as Nth from a person's राशि —

| Transiting Moon in | Result |
|---|---|
| 1st, 3rd, 6th, 7th, 10th, 11th | favorable (11th auspicious for ALL planets) |
| 2nd, 4th, 5th, 9th, 12th | unfavorable |
| **8th = चन्द्राष्टम** | **most unfavorable** |

([Phaladeepika Ch.26, wisdomlib](https://www.wisdomlib.org/hinduism/book/phaladeepika-by-mantreswara-text-and-translation/d/doc1621598.html); [Brihat Samhita Ch.104, wisdomlib](https://www.wisdomlib.org/hinduism/book/brihat-samhita/d/doc229368.html))

**चन्द्राष्टम**: the ~48-hour window (~every 27 days) of Moon in the 8th from one's राशि — mental unease, avoid new ventures. Nepali पात्रो apps surface a daily "आजको चन्द्राष्टम" list. Classical relief: cancelled if Moon transits the 15th/17th/19th नक्षत्र from birth-star. ([AstroBhava](https://astrobhava.com/chandrashtama/))

### 3b. वेध (obstruction)

A favorable transit is **cancelled** if another planet (not Mercury; Sun/Moon never obstruct each other) occupies the paired house. Moon's pairs (फलदीपिका): 1st↔5th, 3rd↔9th, 6th↔12th, 7th↔2nd, 10th↔4th, 11th↔8th.

### 3c. General planetary transit table (बृहत्संहिता Ch.104)

| Planet | Favorable houses from राशि |
|---|---|
| सूर्य | 3, 6, 10, 11 |
| चन्द्र | 1, 3, 6, 7, 10, 11 |
| मङ्गल | 3, 6, 11 |
| बुध | 2, 4, 6, 8, 10, 11 |
| गुरु | 2, 5, 7, 9, 11 |
| शुक्र | 1,2,3,4,5,8,9,11,12 (malefic 6,7,10) |
| शनि | 3, 6, 11 |

A defensible rule-based दैनिक राशिफल = today's Moon sign + this table's 12-fold rotation + वेध modifiers + चन्द्राष्टम flag — **every element a public-domain classical rule**.

## 4. पञ्चाङ्ग elements + साइत/मुहूर्त

पञ्चाङ्ग = five limbs from Sun–Moon geometry, **sunrise-referenced and location-dependent** (Kathmandu standard):

| Element | Definition | Count |
|---|---|---|
| **तिथि** | Lunar day = 12° of Moon–Sun elongation; शुक्ल/कृष्ण पक्ष | 30/month |
| **वार** | Weekday | 7 |
| **नक्षत्र** | Moon's lunar mansion (13°20′ each) | 27 |
| **योग** | Sun+Moon longitude combination | 27 |
| **करण** | Half-तिथि (6°); 4 fixed + 7 repeating | 11 |

Common साइत/मुहूर्त items: **राहुकाल** (inauspicious ~90-min window by weekday), **अभिजित मुहूर्त** (auspicious around solar noon), **चौघडिया** (8 day + 8 night ~90-min slots: शुभ/लाभ/अमृत/चर good; काल/रोग/उद्वेग bad), **साइत** = elected auspicious moment (NPNS publishes national ones, e.g. Dashain tika).

## 5. Bikram Sambat + नेपाल पञ्चाङ्ग निर्णायक समिति

**BS**: Nepal's official calendar, ~56.7 years ahead of Gregorian; **solar** — months bounded by **सङ्क्रान्ति** (Sun entering each sign), month lengths 29–32 days **fixed annually by astronomical computation, not fixed rule**; New Year १ बैशाख (~13–15 April). ([Vikram Samvat, Wikipedia](https://en.wikipedia.org/wiki/Vikram_Samvat))

**NPNS (नेपाल पञ्चाङ्ग निर्णायक विकास समिति)** — government body (Ministry of Culture; Narayanhiti complex) that **standardizes and certifies the national पञ्चाङ्ग**. First Nepali patro: **Pandit Toyanath Pant, 1946 BS**; computation reformed by **Pandit Hemraj Sharma** ~1961 BS; committee certification from ~2035 BS; reconstituted by the **गठन आदेश २०७७** ([Nepal Law Commission](https://lawcommission.gov.np/content/12400/12400-nepal-panchang-adjudicatory-de/)). **No patro may legally be published in Nepal without NPNS approval**; it fixes month lengths, festival dates, national साइत. ([npns.gov.np](https://npns.gov.np/))

**Implication:** panchanga values should match the NPNS-approved patro or be computed for Kathmandu and clearly labeled.

## 6. Classical source inventory + public-domain assessment

Original works: authors centuries dead → unambiguously PD. **Modern translations/commentaries are separately copyrighted** — use original text or out-of-copyright editions.

| Text | Author | Date | Contains | PD status |
|---|---|---|---|---|
| **बृहत्संहिता** | Varāhamihira | 6th c. | Ch.104 transit tables | PD |
| **बृहज्जातक** | Varāhamihira | 6th c. | Predictive foundations | PD |
| **सारावली** | Kalyāṇavarma | 10th c. | Yogas & phala | PD |
| **फलदीपिका** | Mantreśvara | ~13th–15th c. | Ch.26 Moon transit + वेध | PD |
| **मुहूर्तचिन्तामणि** | Rāma Daivajña | 1600 CE | Muhūrta/साइत rules | PD |
| **बृहत्पराशरहोराशास्त्र** | attrib. Parāśara | ancient | Broad system | PD |

Free full texts: archive.org, wisdomlib.org.

### Nepali-language candidates (the mission tie-in)
- **दैवज्ञ बलभद्र जोशी** (b. 1494, "Balbhadra of Jumla") — commentary on the *Bhāsvatī* (panchanga-computation text). Firmly PD; a genuinely NEPALI jyotish primary source. ([Wikipedia](https://en.wikipedia.org/wiki/Daibagya_Balbhadra_Joshi))
- **Pandit Toyanath Pant** — first modern Nepali patro (1946 BS); Toyanath Panchanga still published. Early editions may be PD under life+50 — **death-date verification needed**.
- **Pandit Hemraj Sharma** — Rajguru who reformed calendar computation; worth investigating for PD works.

**Recommendation:** classical Sanskrit rule text = citable PD basis; flag early Nepali panchanga/jyotish books (Balbhadra Joshi, early Toyanath) as future archive acquisitions with the standard rights check (Nepal Copyright Act 2059, life+50).

## 7. Register and style of Nepali राशिफल prose

Tone: **warm, second-person, imperative-advisory, gently optimistic**; potential/probabilistic mood **-ला / -नेछ / होला / भइएला**; short clause-chained sentences; standard footer शुभ रंग + शुभ अंक; domains: धन, मान-सम्मान/पद, परिवार/सन्तान, अध्ययन, यात्रा, स्वास्थ्य + one caution.

Verbatim examples:
> **मेष** — "तपाईंको सहयोगले कसैको उद्धार हुनेछ, मनमा शान्ति छाउनेछ। चारैतिरबाट लाभ होला, सन्तान तथा स्त्री सुख प्राप्त होला।" — [Ramro Patro](https://ramropatro.com/rashifal)
> **वृष** — "मान, सम्मान तथा पद प्रतिष्ठा प्राप्ति होला, अधुरा कामहरू सम्पन्न होलान्, अर्थपूर्ण यात्रा होला, तर अपरान्ह तिर भने अप्रिय समाचार सुन्नुपर्ला।" — [Ramro Patro](https://ramropatro.com/rashifal)
> **वृष** — "अधुरा काम पूरा गर्ने समय आएको छ। परिवारले तपाईंको साथ दिनेछन्। पैसा खर्च गर्दा आवश्यक कुरा मात्र रोज्नुहोस्।" — [Hamro Patro](https://www.hamropatro.com/rashifal)

Register signatures: the **mixed-with-caveat** clause ("…तर अपरान्ह तिर…") and the "…गर्नुहोस्" advice imperative.

## The 3 most load-bearing findings

1. **It must be moon-sign (चन्द्र राशि), transit-driven — not sun signs.** Authenticity rests on (a) राशि via the नामाक्षर table / birth data, (b) daily text from today's Moon position relative to that राशि (गोचर), with चन्द्राष्टम as the headline daily flag. A birth-month picker would immediately mark it as generic.

2. **A defensible राशिफल can be generated purely from public-domain classical rules** — बृहत्संहिता Ch.104 tables, फलदीपिका Ch.26 Moon+वेध, चन्द्राष्टम — authors 500–1400 years dead. The feature can *cite its sources* as a rule engine over classical texts. Beware: modern translations are separately copyrighted.

3. **Anchor in Bikram Sambat + Kathmandu + NPNS-consistent panchanga.** Lead with BS date, तिथि, नक्षत्र, वार (Kathmandu-referenced; sunrise-dependent). Prose in the soft potential mood with शुभ रंग/अंक footers. Mission tie-in is real: Balbhadra Joshi's *Bhāsvatī* commentary and early Toyanath Panchanga editions are legitimate future archive acquisitions (rights checks pending).
