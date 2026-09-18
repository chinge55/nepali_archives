"""Roman-to-Devanagari typing-tool page."""

import shutil

from ..assets import asset_version
from ..config import SITE_NAME

def write_type_page(context, page, assets):
    """Copy assets/type/ → SITE/type/ and write the /type/ page."""
    src = context.root / "assets" / "type"
    tdir = context.site / "type"
    tdir.mkdir(exist_ok=True)
    for f in sorted(src.glob("*")):
        if f.is_file() and f.name != "package.json":   # node-ESM marker, not a site asset
            shutil.copy(f, tdir / f.name)
    # Data and module changes share a cache version, including nested imports.
    ver = asset_version("".join(f.read_text(encoding="utf-8") for f in sorted(src.glob("*"))
                               if f.suffix in {".js", ".json"} and f.name != "package.json"))
    body = f"""<h1>नेपालीमा टाइप गर्नुहोस्</h1>
<p class="lead">रोमनबाट नेपाली · mero naam → मेरो नाम</p>
<section id="type-tool" aria-label="नेपाली टाइप गर्ने साधन">
<label class="field-label" for="inp">रोमनमा लेख्नुहोस् <span>· Type in Roman</span></label>
<textarea id="inp" rows="1" autocomplete="off" autocorrect="off" autocapitalize="none" spellcheck="false"
 enterkeyhint="enter" placeholder="mero naam…" aria-describedby="inputhint"></textarea>
<p id="inputhint" class="input-hint">Space ले शब्द रोज्छ · Enter ले नयाँ हरफ सुरु गर्छ</p>
<div id="cands" role="group" aria-label="शब्दका विकल्प · Word suggestions"></div>
<p id="suggestionstatus" class="type-sr" role="status" aria-live="polite" aria-atomic="true"></p>
<div class="tbar primary-actions">
  <button id="copy" type="button">कपी · Copy</button>
  <label class="ttog"><input type="checkbox" id="engmode" checked> English जस्ताको तस्तै</label>
</div>
<label class="field-label" for="out">नेपाली पाठ <span>· Nepali text</span></label>
<div class="outwrap"><div id="outbg" aria-hidden="true"></div><textarea id="out" readonly rows="4"
 aria-describedby="outputhint" placeholder="नेपाली पाठ यहाँ देखिन्छ"></textarea></div>
<p id="outputhint" class="type-sr">रोमनमा माथि लेख्नुहोस्। बनेको नेपाली पाठ यहीँ सच्याउन सकिन्छ। Type above; edit the converted text here.</p>
<div class="tbar edit-actions" role="group" aria-label="पाठ सम्पादन · Edit text">
  <button id="paragraph" type="button" title="Shift+Enter">अनुच्छेद <span>· Paragraph</span></button>
  <button id="undo" type="button" disabled aria-label="फर्काउने · Undo" title="Ctrl/⌘+Z">↶ Undo</button>
  <button id="redo" type="button" disabled aria-label="दोहोर्‍याउने · Redo" title="Ctrl/⌘+Shift+Z">↷ Redo</button>
  <button id="clear" type="button">मेट्ने · Clear</button>
</div>
<p id="toast" role="status" aria-live="polite"></p>
<p id="status" role="status">तयार हुँदैछ… Loading typing tool.</p>
<button id="retry" type="button" hidden>फेरि प्रयास · Retry</button>
<p id="draftstatus" role="status"></p>
</section>
<details class="thelp"><summary>सच्याउने तरिका र सर्टकट · Help &amp; shortcuts</summary>
<p>विकल्प रोज्न थिच्नुहोस्; थप विकल्पका लागि तेर्सो सार्नुहोस्। Tap a suggestion; scroll the row for more.</p>
<p>नेपाली शब्द सच्याउन त्यसलाई select गरेर माथि रोमनमा फेरि लेख्नुहोस्।
खाली रोमन इनपुटमा Backspace थिच्दा नेपाली कर्सरअघिको शब्द फर्किन्छ।</p>
<ul>
<li><kbd>Space</kbd> पहिलो विकल्प · <kbd>Alt+1</kbd>–<kbd>Alt+5</kbd> अरू विकल्प</li>
<li><kbd>Enter</kbd> नयाँ हरफ · <kbd>Shift+Enter</kbd> नयाँ अनुच्छेद</li>
<li><kbd>Esc</kbd> जस्ताको तस्तै राख्ने · Keep as typed</li>
<li><kbd>Ctrl/⌘+Z</kbd> Undo · <kbd>Ctrl/⌘+Shift+Z</kbd> Redo</li>
</ul>
<p>English शब्दको ठूलो/सानो अक्षर उस्तै रहन्छ। इमेल, वेब ठेगाना र covid19 जस्ता मिश्रित शब्द जस्ताको तस्तै रहन्छन्।</p>
<p>ट/ठ/ड/ढ/ण/ष का लागि <kbd>T</kbd>/<kbd>Th</kbd>/<kbd>D</kbd>/<kbd>Dh</kbd>/<kbd>N</kbd>/<kbd>S</kbd>
प्रयोग गर्न सकिन्छ (bheTaula → भेटौला)।</p>
<p>पाठ यस ब्राउजरमा मात्र सुरक्षित हुन्छ। मेटेको पाठ पृष्ठ बन्द गर्नुअघि Undo गरेर फर्काउन सकिन्छ।
Drafts stay in this browser. Clear can be undone until you leave the page.</p>
</details>
<noscript><p>टाइप गर्न JavaScript चाहिन्छ · Enable JavaScript to use the typing tool.</p></noscript>
<script type="module" src="app.js?v={ver}" data-v="{ver}"></script>
"""
    (tdir / "index.html").write_text(
        page("नेपालीमा टाइप गर्नुहोस् — रोमनबाट नेपाली युनिकोड · " + SITE_NAME, body,
             desc="रोमनमा लेखेर नेपाली युनिकोडमा पाउनुहोस् (mero naam → मेरो नाम) — Type in Nepali online, Roman to Nepali Unicode converter",
             css_depth=1, extra_head=f"<style>{assets.type_css}</style>\n",
             active="type", canon="type/"),
        encoding="utf-8")
