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
<div class="ch-heading"><div><p class="ch-eyebrow">लेखन साधन</p>
<h1>छन्दमा लेख्नुहोस्</h1>
<p class="lead">आफ्ना शब्द लेख्नुहोस्। अक्षर, लघु–गुरु र लय सँगसँगै हेर्नुहोस्।</p></div>
<span class="ch-edition">अभ्यास संस्करण</span></div>
<section id="chhanda-tool" aria-label="छन्द लेखन सहायक">
<fieldset class="ch-metres"><legend>१. छन्द छान्नुहोस्</legend>
<div id="metre-choices" class="ch-metre-options"></div></fieldset>
<div class="ch-workspace">
<section class="ch-editor-card" aria-labelledby="editor-heading">
<div class="ch-section-top"><h2 id="editor-heading">२. आफ्नो कविता</h2>
<button type="button" id="example-open" class="ch-text-button">उदाहरण हेर्नुहोस् ↗</button></div>
<label for="poem" class="ch-sr">कविताको पाठ</label>
<textarea id="poem" rows="7" spellcheck="false" autocorrect="off" autocapitalize="none"
 placeholder="यहाँ आफ्नो पहिलो पाउ लेख्नुहोस्…" aria-describedby="editor-hint"></textarea>
<p id="editor-hint" class="ch-caption">नयाँ हरफ वा / ले अर्को पाउ सुरु गर्छ। खाली हरफले अर्को श्लोक छुट्याउँछ।</p>
<div class="ch-editor-live"><span id="editor-live-status"></span><span id="editor-live-pattern"></span></div>
<div class="ch-editor-actions"><div class="ch-action-group">
<button type="button" id="undo" disabled title="Ctrl/⌘+Z">↶ <span>फर्काउने</span></button>
<button type="button" id="redo" disabled title="Ctrl/⌘+Shift+Z">↷ <span>दोहोर्‍याउने</span></button>
<button type="button" id="boundary" title="कर्सरमा पाउ छुट्याउने / राख्नुहोस्">/ पाउ</button></div>
<button type="button" id="copy">कपी गर्नुहोस्</button></div>
<details id="roman-panel" class="ch-roman"><summary>रोमनबाट नेपाली लेख्नुहोस्</summary>
<label for="roman">रोमनमा एक शब्द</label><div class="ch-roman-row">
<input id="roman" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" placeholder="kabita">
<button id="roman-retry" type="button" hidden>फेरि प्रयास</button></div>
<div id="roman-choices" class="ch-candidates" role="group" aria-label="नेपाली शब्दका विकल्प"></div>
<p id="roman-status" class="ch-caption">विकल्प थिच्दा कवितामा कर्सर भएको ठाउँमा शब्द बस्छ।</p></details>
<div class="ch-draft-row"><span id="draft-status">पाठ यस ब्राउजरमा मात्र सुरक्षित हुन्छ।</span>
<button type="button" id="clear" class="ch-text-button">नयाँ सुरु</button></div>
</section>
<aside class="ch-guide" aria-labelledby="guide-heading"><p class="ch-eyebrow">छन्दको ढाँचा</p>
<h2 id="guide-heading">भुजङ्गप्रयात</h2><p id="metre-description"></p>
<div id="metre-pattern" class="ch-formula" aria-label="लघु गुरुको क्रम"></div>
<p id="metre-ganas" class="ch-caption"></p><p id="pause-note" class="ch-caption"></p>
<div class="ch-legend"><span><b>ल</b> लघु · १ मात्रा</span><span><b>ग</b> गुरु · २ मात्रा</span></div>
<label class="ch-flex"><input type="checkbox" id="final-flexible" checked> पाउको अन्तिम लघुलाई गुरु मान्ने छुट</label>
<p class="ch-caption">काव्यपाठमा शब्दको अन्तिम ‘अ’ उच्चारित मानेर गणना हुन्छ। तलको उच्चारण विकल्पबाट बदल्न सकिन्छ।</p>
</aside></div>
<section class="ch-analysis" aria-labelledby="analysis-heading">
<div class="ch-section-top"><h2 id="analysis-heading">३. अक्षर र लय</h2><span id="active-label" class="ch-caption">पहिलो पाउ</span></div>
<p id="boot-status" role="status">लेखन सहायक तयार हुँदैछ…</p>
<button id="boot-retry" type="button" hidden>फेरि प्रयास गर्नुहोस्</button>
<div id="pada-tabs" class="ch-pada-tabs" role="group" aria-label="पाउका नतिजा"></div>
<div class="ch-analysis-top"><p id="analysis-status"></p><span id="counts" class="ch-caption"></span></div>
<div class="ch-scansion-wrap" tabindex="0" role="region" aria-label="अक्षर र अपेक्षित लघु गुरुको तुलना"><div id="scansion" class="ch-scansion"></div></div>
<p id="syllable-detail" class="ch-syllable-detail">अक्षर थिचेर लघु वा गुरु हुनुको कारण हेर्नुहोस्।</p>
<p id="analysis-hint" class="ch-caption"></p>
<details id="reading-panel"><summary>शब्दको उच्चारण मिलाउनुहोस् <span id="reading-count"></span></summary>
<p class="ch-caption">अन्तिम ‘अ’ उच्चारित छ कि छैन भन्ने आफ्नो पाठअनुसार छान्नुहोस्। छन्द मिलाउन पाठ आफैँ बदलिँदैन।</p>
<div id="reading-choices" class="ch-reading-choices"></div></details>
<div id="stanza-summary" class="ch-caption"></div>
</section>
<section class="ch-suggestions" aria-labelledby="suggestion-heading"><div class="ch-section-top">
<div><p class="ch-eyebrow">अर्को शब्द खोज्दा</p><h2 id="suggestion-heading">लयमा मिल्ने शब्द</h2></div>
<label class="ch-prefix-label" for="word-prefix">सुरुको अक्षर <input id="word-prefix" placeholder="जस्तै: म" autocomplete="off"></label></div>
<p id="suggestion-context" class="ch-caption">पाउको बाँकी ढाँचामा मिल्ने शब्दहरू यहाँ देखिन्छन्।</p>
<div id="word-choices" class="ch-candidates" role="group" aria-label="ढाँचामा मिल्ने शब्दहरू"></div>
<div id="word-preview" class="ch-preview" hidden><p id="preview-line"></p>
<button id="insert-word" type="button">यो शब्द राख्नुहोस्</button><button id="cancel-preview" type="button">रद्द</button></div>
<p class="ch-caption">यी तौलमा मिल्ने विकल्प हुन्। अर्थ र भावअनुसार शब्द आफैँ रोज्नुहोस्। शब्द छानेर त्यसको ठाउँमा अर्को शब्द पनि खोज्न सकिन्छ।</p></section>
<details id="example-panel" class="ch-example"><summary>देवकोटाको कविताबाट सिक्नुहोस्</summary>
<blockquote id="example-text"></blockquote><p><a id="example-source" href="https://www.nepaliarchives.org/authors/devkota/shakuntala/">शाकुन्तल</a></p>
<p id="example-page" class="ch-caption"></p><button id="use-example" type="button">यो उदाहरण सम्पादकमा राख्नुहोस्</button>
<p class="ch-caption">लेखिरहेको पाठ फेरिन्छ; फर्काउने बटनले पहिलेकै पाठ फिर्ता ल्याउँछ।</p></details>
<div class="ch-export"><button id="download-text" type="button">पाठ डाउनलोड · TXT</button>
<button id="export-project" type="button">मस्यौदा सुरक्षित गर्नुहोस्</button>
<label class="ch-file-button">मस्यौदा खोल्नुहोस्<input id="import-project" type="file" accept="application/json,.json"></label></div>
<p id="notice" class="ch-caption" role="status" aria-live="polite"></p>
<details class="ch-help"><summary>यो सहायकले कसरी जाँच्छ?</summary>
<p>दीर्घ स्वर, अनुस्वार, विसर्ग र संयुक्त व्यञ्जनका आधारमा अक्षरको तौल देखाइन्छ। चन्द्रबिन्दुले मात्र ह्रस्व स्वरलाई गुरु बनाउँदैन।
लघु–गुरुको क्रम छानिएको छन्दसँग तुलना हुन्छ। यहाँ “अक्षर” भन्नाले उच्चारणको एकाइ बुझिन्छ।</p>
<p>यो प्रारम्भिक, नियममा आधारित अभ्यास सहायक हो। विशेष काव्यपाठ, सन्धि, संयुक्त व्यञ्जनका फरक उच्चारण र कविले लिएको छुटमा फरक नतिजा आउन सक्छ।
नतिजालाई आफ्नो उच्चारण र छन्दको अध्ययनसँग दाँज्नुहोस्। मिलेको तौलले कविताको अर्थ वा गुणको मूल्याङ्कन गर्दैन।</p>
<p>उदाहरणको पाठ मूल पृष्ठसँग तुलना गरिएको छ। छन्दका सूत्रका लागि <a href="https://chhanda.vag.org.np/Examples/">छन्दःशिक्षा</a> र
<a href="https://www.sanskrit-lexicon.uni-koeln.de/scans/csldev/csldoc/build/dictionaries/prefaces/ap90app1.html">आप्टेको छन्द परिचय</a> हेर्न सकिन्छ।</p>
<p>पाठ वा मस्यौदा कतै पठाइँदैन। यो ब्राउजरको तथ्याङ्क मेटिँदा स्थानीय मस्यौदा पनि मेटिन्छ; फाइलमा सुरक्षित गर्न सकिन्छ।</p></details>
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
