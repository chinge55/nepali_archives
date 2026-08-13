"""Public description and execution graph for scanned-book OCR."""

from ..config import SITE_NAME

def write_ocr_page(context, page):
    """Write the provider-neutral account of the scanned-book DAG in Nepali."""
    out = context.site / "ocr"
    out.mkdir(parents=True, exist_ok=True)
    arrow = '<div class="flow-arrow" aria-hidden="true">↓</div>'
    body = f"""<nav class="crumb"><a href="../about.html">← बारेमा</a></nav>
<article class="ocr-page">
<header class="ocr-hero">
  <p class="ocr-kicker">हाम्रो OCR विधि</p>
  <h1>स्क्यानदेखि पाठसम्म</h1>
  <p class="ocr-dek">एउटा पुरानो पुस्तक, धेरै सावधान पढाइ—र एउटै नियम: मूलप्रति इमानदार।</p>
</header>
<p>स्क्यानमा भेटिएको नेपाली पुस्तकलाई पढ्न मिल्ने डिजिटल पाठमा उतार्नु केवल OCR चलाउनु होइन।
पहिले मेसिनले सम्भावित अक्षर देखाउँछ; त्यसपछि अलग-अलग एजेन्टले पृष्ठ हेरेर पुस्तकको बनोट,
पानाको क्रम, मूल पाठ र पादटिप्पणी मिलाउँछन्।</p>
<aside class="ocr-principle">
  <span aria-hidden="true">“</span>
  <p><strong>हाम्रा लागि छापिएको पृष्ठ नै प्रमाण हो।</strong> OCR ले बाटो देखाउँछ, एजेन्टले पढ्छन्;
  तर नदेखिएको कुरा अनुमान गरेर भरिँदैन।</p>
</aside>
<p>त्यसैले पुरानो हिज्जे, विरामचिह्न, अनौठो शब्द र मूलमै भएका खाली ठाउँ जस्ताको तस्तै रहन्छन्।
कुनै अंशमा भरोसा गर्न नसकिए काम अघि बढ्दैन—त्यहीँ रोकिन्छ।</p>

<h2>काम बाँडिएको छ—जिम्मेवारी पनि</h2>
<p class="section-intro">कुनै एउटै एजेन्टले पुस्तक उठाएर सीधै अभिलेखमा राख्दैन। हरेक पक्षले
आफ्नो सीमाभित्रको काम गर्छ, र अर्को पक्षले त्यसलाई जाँच्छ।</p>
<div class="ocr-roles">
  <div class="role-agent"><span class="role-mark" aria-hidden="true">प</span><h3>पठन एजेन्ट</h3>
  <p>पृष्ठ हेर्छन्, पुस्तकको बनोट बुझ्छन्, मुद्रित पानाको क्रम मिलाउँछन् र मूल पाठ तथा
  पादटिप्पणी पढ्छन्। शङ्का परेको अंश अर्को एजेन्टले फेरि हेर्छ।</p></div>
  <div class="role-coord"><span class="role-mark" aria-hidden="true">स</span><h3>समन्वय एजेन्ट</h3>
  <p>फरक पढाइका प्रमाण जोडेर एउटै संरचना योजना बनाउँछ र स्वीकृत सामग्रीबाट प्रस्तावित
  कृति फाइल तयार गर्छ। ती फाइल मुख्य अभिलेखबाहिरै रहन्छन्।</p></div>
  <div class="role-software"><span class="role-mark" aria-hidden="true">औ</span><h3>स्थानीय औजार</h3>
  <p>पृष्ठचित्र र OCR बनाउँछन्, नियमले गुणस्तर जाँच्छन्, फाइल नबदलिएको प्रमाण राख्छन्
  र स्वीकृत फाइल मात्र अभिलेखमा सार्छन्।</p></div>
  <div class="role-human"><span class="role-mark" aria-hidden="true">म</span><h3>मानिस</h3>
  <p>कुन सामग्री राख्ने भन्ने योजना र प्रकाशनमा जाने ठ्याक्कै फाइल—दुवै छुट्टाछुट्टै
  स्वीकृत गर्छ। दुई पुनःजाँचले नसुल्झाएको अंश पनि मानिसकै लागि रोकिन्छ।</p></div>
</div>

<aside class="agent-boundary">
  <p class="boundary-label">एजेन्टको सीमा</p>
  <p>एजेन्टले लेखकको भाषा “सुधार्दैन”, नदेखिएको श्लोक वा अक्षर थप्दैन, आफैँ प्रकाशन
  स्वीकृत गर्दैन र कुनै पाठलाई प्रुफरिड भएको घोषणा गर्दैन।</p>
</aside>

<h2 id="graph-title">एउटा पुस्तकले हिँड्ने बाटो</h2>
<p class="section-intro">तलको नक्सा हाम्रो वास्तविक कामकै सरल रूप हो। समान तहका पढाइहरू
सँगसँगै वा पालैपालो चल्न सक्छन्।</p>
<div class="flow-legend" aria-label="जिम्मेवारी सङ्केत">
  <span class="who agent">पठन एजेन्ट</span>
  <span class="who coord">समन्वय एजेन्ट</span>
  <span class="who software">स्थानीय औजार</span>
  <span class="who human">मानिस</span>
</div>
<figure class="ocr-journey" aria-labelledby="graph-title graph-caption">
  <div class="journey-source"><span>मूल</span><strong>स्रोत पुस्तकको PDF</strong><small>पृष्ठचित्र नै अन्तिम प्रमाण</small></div>
  {arrow}
  <section class="journey-phase phase-one">
    <header class="phase-head"><span class="phase-number">१</span><div><p>पहिलो चरण</p><h3>पुस्तक चिन्नु</h3>
    <small>पाठ उतार्नुअघि पुस्तककै नक्सा बनाइन्छ।</small></div></header>
    <div class="mechanical-run">
      <div><span class="who software">स्थानीय औजार</span><strong>स्रोत दर्ता</strong><small>बीचमा रोकिए पनि फेरि सुरु गर्न मिल्ने गरी</small></div>
      <i aria-hidden="true">→</i>
      <div><span class="who software">स्थानीय औजार</span><strong>सुरुआती जाँच</strong><small>PDF, स्रोत र लेखकको आधारभूत विवरण</small></div>
      <i aria-hidden="true">→</i>
      <div><span class="who software">स्थानीय औजार</span><strong>पृष्ठचित्र र धेरै OCR पढाइ</strong><small>हरेक पृष्ठलाई एकभन्दा बढीपटक पढाइन्छ</small></div>
    </div>
    <p class="fan-label">त्यसपछि तीन स्वतन्त्र नजर</p>
    <div class="flow-grid three">
      <div class="flow-card agent"><span class="who agent">गहिरो पठन</span><strong>भित्र के-के छ?</strong><small>कृति, खण्ड, लेखकको आफ्नै भूमिका र हटाउनुपर्ने आधुनिक सामग्री</small></div>
      <div class="flow-card agent"><span class="who agent">द्रुत जाँच</span><strong>पाना सही क्रममा छन्?</strong><small>मुद्रित पृष्ठाङ्क पढेर उल्टापुल्टा स्क्यान पत्ता लगाउने</small></div>
      <div class="flow-card agent"><span class="who agent">द्रुत जाँच</span><strong>कृति पहिल्यै छ?</strong><small>अभिलेखसँग नाम र विवरण मिलाएर दोहोरोपन रोक्ने</small></div>
    </div>
    {arrow}
    <div class="flow-card coord wide"><span class="who coord">समन्वय एजेन्ट</span><strong>तीनै पढाइ जोडेर पुस्तकको एउटै नक्सा</strong><small>हरेक पृष्ठ राखिएको, हटाइएको वा कुनै कृतिसँग जोडिएको हुन्छ।</small></div>
    {arrow}
    <div class="approval-card"><span class="approval-seal" aria-hidden="true">✓</span><div><span class="who human">मानिस</span><strong>पहिलो स्वीकृति</strong><small>पृष्ठक्रम, कृति-विभाजन र हटाइने सामग्री हेरेर मात्र योजना स्वीकार हुन्छ।</small></div></div>
  </section>
  {arrow}

  <section class="journey-phase phase-two">
    <header class="phase-head"><span class="phase-number">२</span><div><p>दोस्रो चरण</p><h3>पाठ उतार्नु</h3>
    <small>स्वीकृत प्रत्येक कविता, सर्ग वा निबन्ध पूरा खण्डका रूपमा पढिन्छ।</small></div></header>
    <div class="phase-note"><span class="who software">स्थानीय औजार</span> हरेक खण्डका लागि छुट्टै काम खोल्छ</div>
    <p class="fan-label">एउटै खण्डमाथि दुई छुट्टाछुट्टै नजर</p>
    <div class="flow-grid two">
      <div class="flow-card agent"><span class="who agent">गहिरो पठन</span><strong>पृष्ठसँग पाठ मिलाउने</strong><small>OCR लाई सङ्केत मानेर पूरा खण्ड अक्षरशः उतार्ने; लेखकको भाषा नछुने</small></div>
      <div class="flow-card agent"><span class="who agent">द्रुत जाँच</span><strong>पादटिप्पणी खोज्ने</strong><small>हरेक पृष्ठको पुछार र पाठमा भएका टिपोटका सङ्केत छुट्टै हेर्ने</small></div>
    </div>
    {arrow}
    <div class="flow-card software wide"><span class="who software">स्थानीय औजार</span><strong>नियमले फेरि जाँच्छ</strong><small>सबै पृष्ठ समेटिए? अङ्क बिग्रिए? पादटिप्पणी छुट्यो? अनावश्यक शीर्षक मिसियो?</small></div>
    <div class="decision-card">
      <p>ठूलो शङ्का बाँकी छ?</p>
      <div class="decision-paths">
        <div class="pass-path"><span>छैन</span><strong>अर्को चरणमा जान्छ</strong></div>
        <div class="review-path"><span>छ</span><strong>अर्को पठन एजेन्टले शङ्का लागेको पृष्ठ फेरि हेर्छ</strong>
        <small>औजारले पुनः जाँच्छ—बढीमा दुई चक्र। त्यसपछि पनि नसुल्झिए मानिसका लागि रोकिन्छ।</small></div>
      </div>
    </div>
    <p class="phase-exit">जोखिम हटेपछि मात्रै अभिलेखका फाइल तयार हुन्छन्।</p>
  </section>
  {arrow}

  <section class="journey-phase phase-three">
    <header class="phase-head"><span class="phase-number">३</span><div><p>तेस्रो चरण</p><h3>अभिलेखमा राख्नु</h3>
    <small>पाठ तयार हुनु र प्रकाशनका लागि स्वीकार हुनु फरक कुरा हुन्।</small></div></header>
    <div class="flow-card coord wide"><span class="who coord">समन्वय एजेन्ट</span><strong>कृति फाइलको मस्यौदा बनाउँछ</strong><small>पाठ, विवरण र स्रोत PDF मुख्य अभिलेखभन्दा बाहिरको सुरक्षित ठाउँमा तयार हुन्छन्।</small></div>
    {arrow}
    <div class="flow-card software wide"><span class="who software">स्थानीय औजार</span><strong>मस्यौदा पूरै जाँच्छ</strong><small>ढाँचा, फाइलको ठाउँ, स्रोत PDF र बदलिन लागेका फाइल—सबै मिल्नुपर्छ।</small></div>
    {arrow}
    <div class="approval-card"><span class="approval-seal" aria-hidden="true">✓</span><div><span class="who human">मानिस</span><strong>दोस्रो स्वीकृति</strong><small>अभिलेखमा जाने ठ्याक्कै फाइल हेरेर मात्रै प्रकाशन स्वीकार हुन्छ।</small></div></div>
    {arrow}
    <div class="flow-card software wide"><span class="who software">स्थानीय औजार</span><strong>स्वीकृत फाइल मात्र सार्छ</strong><small>फेरि एकपटक जाँचेर मुख्य अभिलेखमा राख्छ र परिवर्तनको अभिलेख बनाउँछ।</small></div>
  </section>
  {arrow}
  <div class="journey-finish"><span aria-hidden="true">अ</span><div><strong>अभिलेखका स्रोत फाइल</strong><small>पाठ · विवरण · स्रोत PDF</small></div></div>
  <figcaption id="graph-caption">स्वीकृत फाइल पछि बदलियो भने स्वीकृति आफैँ अमान्य हुन्छ।
  दोस्रो स्वीकृतिअघि कुनै एजेन्टले मुख्य अभिलेखमा सीधै लेख्दैन।</figcaption>
</figure>

<h2>जहाँ गल्ती सजिलै लुक्छ</h2>
<p class="section-intro">OCR को ठूलो भूल प्रायः ठूलो देखिँदैन। एउटा उल्टिएको पाना, हराएको
श्लोक अङ्क वा छुटेको सानो पादटिप्पणीले नै पाठको अर्थ बिगार्न सक्छ। त्यसैले यी ठाउँमा हामी
छुट्टै नजर लगाउँछौँ:</p>
<div class="audit-grid">
  <div><strong>पानाको क्रम</strong><span>मुद्रित पृष्ठाङ्क आफैँ पढेर</span></div>
  <div><strong>श्लोकका अङ्क</strong><span>छापिएको छ भने मात्र राखेर</span></div>
  <div><strong>पृष्ठको पुछार</strong><span>छोटा पादटिप्पणी नछुटाई</span></div>
  <div><strong>पाठ र सजावट</strong><span>दोहोरिने शीर्षक र पृष्ठाङ्क हटाएर</span></div>
  <div><strong>कुन अंश राख्ने?</strong><span>लेखकको भूमिका राखी आधुनिक सम्पादकीय अंश हटाएर</span></div>
</div>

<aside class="ocr-status">
  <p class="status-label">एउटा महत्त्वपूर्ण फरक</p>
  <h2>OCR सम्पन्न ≠ प्रुफरिड</h2>
  <p>यो प्रक्रियाले स्रोतसँग मिलाइएको, जाँचिएको OCR पाठ दिन्छ। तर सुरुदेखि अन्त्यसम्म मूलसँग
  फेरि औपचारिक जाँच नभएसम्म हामी त्यसलाई “प्रुफरिड” भन्दैनौँ। त्यसपछि मात्रै विवरणमा
  <code>proofread: true</code> लेखिन्छ।</p>
</aside>

<h2>यो प्रक्रिया पुनःचलाउन</h2>
<p>यो नक्सा देखाउनका लागि मात्र होइन। हरेक कामको सामग्री, अपेक्षित नतिजा, पुनःजाँचको सीमा
र मानवीय स्वीकृतिका ठाउँ सार्वजनिक स्रोतमा खुला छन्। यसका लागि कुनै खास कम्पनीको सेवा
अनिवार्य छैन; आफ्नो जिम्मा पूरा गर्न सक्ने एजेन्ट भए यही विधि अरूले पनि चलाउन सक्छन्।</p>
<a class="ocr-source" href="https://github.com/chinge55/nepali_archives/blob/main/docs/ocr-workflow.md"
   target="_blank" rel="noopener">
  <span class="source-mark" aria-hidden="true">&lt;/&gt;</span>
  <span><strong>स्रोत कोड र चलाउने विधि</strong><small>कार्यप्रवाह · जिम्मेवारी · जाँचका नियम</small></span>
  <span class="source-arrow" aria-hidden="true">↗</span>
</a>
<p class="meta ocr-version">कार्यप्रवाह संस्करण १ · पछिल्लो संशोधन: २०२६-०८-१३</p>
</article>"""
    (out / "index.html").write_text(
        page("स्क्यानदेखि पाठसम्म — " + SITE_NAME, body,
             desc="नेपाली अभिलेखको प्रदायक-निरपेक्ष OCR र एआई एजेन्ट कार्यप्रवाह",
             css_depth=1, active="about", canon="ocr/"),
        encoding="utf-8")
