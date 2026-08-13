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
    ver = asset_version((src / "app.js").read_text(encoding="utf-8")
               + (src / "engine.js").read_text(encoding="utf-8"))
    body = f"""<h1>नेपालीमा टाइप गर्नुहोस्</h1>
<p class="lead">रोमनमा लेख्नुहोस् (mero naam…) — नेपाली युनिकोडमा पाउनुहोस्। Type in Nepali:
Roman to Nepali Unicode, free and offline-capable.</p>
<div class="outwrap"><div id="outbg" aria-hidden="true"></div><textarea id="out" readonly
 aria-label="नेपाली पाठ (सच्याउन मिल्छ)"
 placeholder="नेपाली यहाँ आउँछ — सच्याउन यहीँ मिल्छ (editable)"></textarea></div>
<div class="tbar">
  <button id="copy" type="button">कपी गर्नुहोस् · Copy</button>
  <button id="clear" type="button">मेट्नुहोस् · Clear</button>
  <span id="toast" role="status" aria-live="polite"></span>
  <label class="ttog"><input type="checkbox" id="engmode" checked> English शब्द English मै</label>
</div>
<div id="cands"></div>
<input id="inp" autocomplete="off" autocorrect="off" autocapitalize="none" spellcheck="false"
 enterkeyhint="done" placeholder="yahan lekhnus… (space = पहिलो रोज्ने)" aria-label="रोमन नेपाली इनपुट">
<p class="thelp">
<kbd>space</kbd>/<kbd>enter</kbd> पहिलो उम्मेदवार रोज्छ · <kbd>1</kbd>–<kbd>5</kbd> अरू रोज्ने ·
<kbd>backspace</kbd> (खाली इनपुटमा) अघिल्लो शब्द सच्याउने · <kbd>esc</kbd> जस्ताको तस्तै राख्ने<br>
माथिको नेपाली सीधै सच्याउन मिल्छ — शब्द select गरेर रोमनमा फेरि लेखे त्यहीँ बस्छ।<br>
Optional: <kbd>T</kbd>=ट <kbd>Th</kbd>=ठ <kbd>D</kbd>=ड <kbd>Dh</kbd>=ढ <kbd>N</kbd>=ण <kbd>S</kbd>=ष
(bheTaula → भेटौला)</p>
<p id="status"></p>
<script type="module" src="app.js?v={ver}" data-v="{ver}"></script>"""
    (tdir / "index.html").write_text(
        page("नेपालीमा टाइप गर्नुहोस् — रोमनबाट नेपाली युनिकोड · " + SITE_NAME, body,
             desc="रोमनमा लेखेर नेपाली युनिकोडमा पाउनुहोस् (mero naam → मेरो नाम) — Type in Nepali online, Roman to Nepali Unicode converter",
             css_depth=1, extra_head=f"<style>{assets.type_css}</style>\n",
             active="type", canon="type/"),
        encoding="utf-8")
