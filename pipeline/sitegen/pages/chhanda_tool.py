"""Browser-local Nepali chhanda writing assistant."""

import shutil

from ..assets import asset_version
from ..config import SITE_NAME


def write_chhanda_page(context, page):
    source = context.root / "assets" / "chhanda"
    target = context.site / "chhanda"
    target.mkdir(exist_ok=True)
    files = sorted(p for p in source.iterdir() if p.is_file() and p.name != "package.json")
    typing_dependencies = sorted(
        p for p in (context.root / "assets" / "type").iterdir()
        if p.suffix in {".js", ".json"} and p.name != "package.json"
    )
    version = asset_version("".join(p.read_text(encoding="utf-8") for p in files + typing_dependencies))
    for path in files:
        shutil.copy(path, target / path.name)
    body = """
<div class="ch-heading"><h1>छन्द लेखन</h1><span class="ch-edition">अभ्यास संस्करण</span></div>
<section id="chhanda-tool" aria-label="छन्द लेखन सहायक">
<section class="ch-editor-card" aria-label="कविता सम्पादक">
<div class="ch-writer-toolbar">
<label class="ch-metre-label" for="metre-select">छन्द <select id="metre-select" aria-label="छन्द छान्नुहोस्"></select></label>
<label class="ch-mode"><span>देवनागरी</span><input id="roman-mode" type="checkbox" role="switch" aria-label="Roman बाट नेपाली लेख्ने"><span>Roman</span></label>
</div>
<label for="poem" class="ch-sr">कविताको पाठ</label>
<textarea id="poem" rows="11" spellcheck="false" autocorrect="off" autocapitalize="none"
 placeholder="आफ्नो कविता यहाँ लेख्नुहोस्…" aria-describedby="editor-live-status"></textarea>
<div id="roman-choices" class="ch-candidates ch-inline-candidates" role="group" aria-label="नेपाली शब्दका विकल्प" hidden></div>
<div class="ch-typing-status"><span id="roman-status"></span><button id="roman-retry" type="button" hidden>फेरि प्रयास</button></div>
<div class="ch-editor-live"><span id="editor-live-status"></span><span id="editor-live-pattern"></span></div>
<div class="ch-editor-actions"><div class="ch-action-group">
<button type="button" id="undo" disabled aria-label="फर्काउने" title="Ctrl/⌘+Z">↶</button>
<button type="button" id="redo" disabled aria-label="दोहोर्‍याउने" title="Ctrl/⌘+Shift+Z">↷</button>
<span id="draft-status" class="ch-caption">यस ब्राउजरमा सुरक्षित</span></div>
<div class="ch-action-group"><button type="button" id="copy">कपी</button>
<details class="ch-file-menu"><summary aria-label="मस्यौदाका थप विकल्प">⋯</summary><div>
<button id="download-text" type="button">पाठ डाउनलोड · TXT</button>
<button id="export-project" type="button">मस्यौदा सुरक्षित गर्नुहोस्</button>
<label class="ch-file-button">मस्यौदा खोल्नुहोस्<input id="import-project" type="file" accept="application/json,.json"></label>
<button type="button" id="clear">नयाँ सुरु</button></div></details></div></div>
</section>
<p id="boot-status" class="ch-caption" role="status">लेखन सहायक तयार हुँदैछ…</p>
<button id="boot-retry" type="button" hidden>फेरि प्रयास गर्नुहोस्</button>
<div class="ch-secondary-tools"><details id="analysis-panel" class="ch-analysis"><summary>लय जाँच्नुहोस्</summary>
<div class="ch-detail-body"><div class="ch-section-top"><span id="active-label" class="ch-caption"></span><span id="counts" class="ch-caption"></span></div>
<div id="pada-tabs" class="ch-pada-tabs" role="group" aria-label="पाउका नतिजा"></div>
<p id="analysis-status"></p>
<div class="ch-scansion-wrap" tabindex="0" role="region" aria-label="अक्षर र अपेक्षित लघु गुरुको तुलना"><div id="scansion" class="ch-scansion"></div></div>
<p id="syllable-detail" class="ch-caption"></p><p id="analysis-hint" class="ch-caption"></p>
<details id="reading-panel"><summary>उच्चारणका विकल्प <span id="reading-count"></span></summary>
<p class="ch-caption">शब्दको अन्तिम ‘अ’ आफ्नो पाठअनुसार छान्नुहोस्।</p><div id="reading-choices" class="ch-reading-choices"></div></details>
<label class="ch-flex"><input type="checkbox" id="final-flexible" checked> पदान्त लघुलाई गुरु मान्ने छुट</label>
<div id="stanza-summary" class="ch-caption"></div></div></details>
<details id="word-panel" class="ch-suggestions"><summary>शब्द खोज्नुहोस्</summary>
<div class="ch-detail-body"><label class="ch-prefix-label" for="word-prefix">सुरुको अक्षर <input id="word-prefix" placeholder="जस्तै: म" autocomplete="off"></label>
<p id="suggestion-context" class="ch-caption"></p><div id="word-choices" class="ch-candidates" role="group" aria-label="ढाँचामा मिल्ने शब्दहरू"></div>
<div id="word-preview" class="ch-preview" hidden><p id="preview-line"></p><button id="insert-word" type="button">यो शब्द राख्नुहोस्</button><button id="cancel-preview" type="button">रद्द</button></div>
<p class="ch-caption">तौलमा मिल्ने विकल्पहरू। अर्थ र भावअनुसार रोज्नुहोस्।</p></div></details>
<button type="button" id="example-open" class="ch-text-button">उदाहरण</button>
<details id="help-panel" class="ch-help"><summary>मद्दत</summary><div class="ch-detail-body">
<h2 id="guide-heading"></h2><p id="metre-description"></p><div id="metre-pattern" class="ch-formula"></div>
<p id="metre-ganas" class="ch-caption"></p><p id="pause-note" class="ch-caption"></p>
<p>ल = लघु, ग = गुरु। नयाँ हरफ वा / ले पाउ छुट्याउँछ; खाली हरफले श्लोक छुट्याउँछ। Roman मा लेख्दा Space वा Enter ले शब्दलाई नेपाली बनाउँछ।</p>
<p>काव्यपाठमा अन्तिम ‘अ’ उच्चारित मानेर गणना हुन्छ। उच्चारणका विकल्पमा यसलाई बदल्न सकिन्छ। दीर्घ स्वर, अनुस्वार, विसर्ग र संयुक्त व्यञ्जनले तौलमा असर गर्छन्; चन्द्रबिन्दुले मात्र ह्रस्व स्वरलाई गुरु बनाउँदैन।</p>
<p>यो प्रारम्भिक अभ्यास सहायक हो। विशेष काव्यपाठ, सन्धि र कविले लिएको छुटमा फरक नतिजा आउन सक्छ। नतिजा आफ्नो पाठसँग दाँज्नुहोस्।</p>
<p>सूत्र: <a href="https://chhanda.vag.org.np/Examples/">छन्दःशिक्षा</a> · <a href="https://www.sanskrit-lexicon.uni-koeln.de/scans/csldev/csldoc/build/dictionaries/prefaces/ap90app1.html">आप्टेको छन्द परिचय</a>।</p>
<p>मस्यौदा यस ब्राउजरमा मात्र रहन्छ। ब्राउजरको तथ्याङ्क मेट्दा यो पनि मेटिन्छ; मस्यौदा फाइलमा सुरक्षित गर्न सकिन्छ।</p></div></details></div>
<p id="notice" class="ch-caption" role="status" aria-live="polite"></p>
<dialog id="example-dialog" class="ch-example"><div class="ch-section-top"><h2>कविताबाट उदाहरण</h2><button id="example-close" type="button" aria-label="उदाहरण बन्द गर्नुहोस्">×</button></div>
<blockquote id="example-text"></blockquote><p><a id="example-source" href="https://www.nepaliarchives.org/authors/devkota/shakuntala/">शाकुन्तल</a></p>
<p id="example-page" class="ch-caption"></p><button id="use-example" type="button">सम्पादकमा राख्नुहोस्</button>
<p class="ch-caption">यसले लेखिरहेको पाठ फेर्छ। फर्काउने बटनबाट पुरानो पाठ फर्कन्छ।</p></dialog>
</section><noscript><p>छन्द जाँच्न JavaScript चाहिन्छ। माथिको बाकसमा पाठ लेख्न र कपी गर्न सकिन्छ।</p></noscript>
"""
    body += f'<script type="module" src="app.js?v={version}"></script>'
    (target / "index.html").write_text(
        page(
            "छन्द लेखन — लघु गुरु जाँच्दै कविता लेख्नुहोस् · " + SITE_NAME,
            body,
            desc="भुजङ्गप्रयात, वसन्ततिलका र शार्दूलविक्रीडितमा कविता लेख्ने निःशुल्क सहायक। लघु गुरु जाँच, शब्दका विकल्प र रोमनबाट नेपाली टाइप।",
            css_depth=1,
            extra_head=f'<link rel="stylesheet" href="chhanda.css?v={version}">',
            active="chhanda",
            canon="chhanda/",
        ),
        encoding="utf-8",
    )
