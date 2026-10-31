// Decorations only: the native textarea owns the text, caret and selection.
export function problemRanges(text, parts, readings) {
  const ranges = [];
  parts.forEach((part, index) => {
    const reading = readings[index];
    if (!reading || ['empty', 'match', 'counted', 'guided', 'typing', 'uncertain'].includes(reading.status)) return;
    const ended = /^[\r\n/|।॥]/.test(text.slice(part.end));
    if (reading.status === 'partial') {
      // An unfinished line is normal while writing. Mark it only after a boundary.
      if (ended && reading.syllables.length) {
        const last = reading.syllables.at(-1);
        ranges.push({ start: part.start + last.start, end: part.start + last.end });
      }
      return;
    }
    reading.slots.forEach((slot, slotIndex) => {
      let syllable = ['mismatch', 'extra'].includes(slot.kind) ? slot.syllable : null;
      if (slot.kind === 'missing') {
        const next = reading.slots.slice(slotIndex + 1).find(s => s.syllable)?.syllable;
        // Internal gaps have visible context; an unwritten tail is left alone.
        syllable = next || (ended ? reading.syllables.at(-1) : null);
      }
      if (syllable) ranges.push({ start: part.start + syllable.start, end: part.start + syllable.end });
    });
  });
  const merged = [];
  for (const range of ranges.sort((a, b) => a.start - b.start)) {
    const last = merged.at(-1);
    if (last && range.start <= last.end) last.end = Math.max(last.end, range.end);
    else merged.push({ ...range });
  }
  return merged;
}

export function createUnderlines(textarea, mirror, layer) {
  let ranges = [], frame;
  const doc = textarea.ownerDocument;
  const typography = ['fontFamily', 'fontSize', 'fontWeight', 'fontStyle', 'fontStretch', 'fontVariant',
    'fontFeatureSettings', 'fontVariationSettings', 'fontKerning', 'letterSpacing', 'lineHeight',
    'wordSpacing', 'textAlign', 'textIndent', 'textTransform', 'direction', 'tabSize',
    'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'];

  function draw() {
    frame = null;
    layer.replaceChildren();
    if (!ranges.length || !textarea.clientWidth) return;
    const style = getComputedStyle(textarea);
    for (const property of typography) mirror.style[property] = style[property];
    mirror.style.width = `${textarea.clientWidth}px`;
    mirror.textContent = textarea.value + (textarea.value.endsWith('\n') ? '\u200b' : '');
    const textNode = mirror.firstChild, origin = textarea.getBoundingClientRect();
    const fragment = doc.createDocumentFragment();
    for (const span of ranges) {
      if (span.start >= textarea.value.length || span.end <= span.start) continue;
      const range = doc.createRange();
      range.setStart(textNode, span.start);
      range.setEnd(textNode, Math.min(span.end, textarea.value.length));
      for (const rect of range.getClientRects()) {
        const left = rect.left - origin.left - textarea.scrollLeft;
        const top = rect.bottom - origin.top - textarea.scrollTop - 1;
        if (top < 0 || top > textarea.clientHeight || left + rect.width < 0 || left > textarea.clientWidth || rect.width < .5) continue;
        const line = doc.createElement('span');
        line.className = 'ch-problem-underline';
        line.dataset.start = String(span.start); line.dataset.end = String(span.end);
        line.style.left = `${left}px`; line.style.top = `${top}px`; line.style.width = `${rect.width}px`;
        fragment.append(line);
      }
    }
    layer.append(fragment);
  }
  function schedule() {
    if (!frame) frame = requestAnimationFrame(draw);
  }
  textarea.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', schedule, { passive: true });
  if (typeof ResizeObserver !== 'undefined') new ResizeObserver(schedule).observe(textarea);
  doc.fonts?.addEventListener('loadingdone', schedule);
  doc.fonts?.ready.then(schedule);
  return {
    update(text, next) {
      // Stale asynchronous analysis must never decorate a newer draft.
      ranges = text === textarea.value ? next : [];
      schedule();
    },
    clear() {
      ranges = []; layer.replaceChildren();
    },
  };
}
