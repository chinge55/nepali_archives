// Inline Roman input: transform only the edited range, keeping editor offsets.
export function changedRange(before, after) {
  let start = 0, end = after.length, oldEnd = before.length;
  while (start < oldEnd && start < end && before[start] === after[start]) start++;
  while (oldEnd > start && end > start && before[oldEnd - 1] === after[end - 1]) { oldEnd--; end--; }
  return { start, end, oldEnd };
}
export function pendingWord(text, caret) {
  let start = caret, end = caret;
  while (/^[A-Za-z]$/.test(text[start - 1] || '')) start--;
  while (/^[A-Za-z]$/.test(text[end] || '')) end++;
  if (start === end) return null;
  if (/[\w@/]/.test(text[start - 1] || '') || /[\w@/]/.test(text[end] || '')) return null;
  let tokenStart = start, tokenEnd = end;
  while (tokenStart > 0 && !/\s/.test(text[tokenStart - 1])) tokenStart--;
  while (tokenEnd < text.length && !/\s/.test(text[tokenEnd])) tokenEnd++;
  if (!/^[A-Za-z]+[.,!?;:।॥]*$/.test(text.slice(tokenStart, tokenEnd))) return null;
  return { start, end, text: text.slice(start, end) };
}
export function transliterateEdit(before, text, caret, convert, { force = false, range } = {}) {
  const area = range || changedRange(before, text);
  let lower = area.start;
  if (!range && /^\s+$/.test(text.slice(area.start, area.end))) {
    // Equal adjacent spaces can make a text diff locate the other space.
    lower = caret;
    while (lower > 0 && /\s/.test(text[lower - 1])) lower--;
    lower = Math.min(lower, area.start);
  }
  let output = '', copied = 0, mappedCaret = caret;
  for (const match of text.matchAll(/\S+/g)) {
    const start = match.index, end = start + match[0].length;
    if (end < lower || start > area.end) continue;
    const token = /^([A-Za-z]+)([.,!?;:।॥]*)$/.exec(match[0]);
    // Existing whitespace after a selected word is not a newly typed boundary.
    if (!token || !force && !(end < area.end || token[2] && end <= area.end)) continue;
    const replacement = convert(token[1]) + token[2].replace(/\./g, '।');
    output += text.slice(copied, start) + replacement; copied = end;
    if (caret >= end) mappedCaret += replacement.length - match[0].length;
    else if (caret > start) mappedCaret += replacement.length - (caret - start);
  }
  return { text: output + text.slice(copied), caret: mappedCaret };
}
