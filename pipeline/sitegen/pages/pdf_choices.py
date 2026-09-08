"""Progressively enhanced PDF edition picker shared by text and PDF readers."""

from ..text import esc


def edition_display_label(edition):
    label = edition["label"]
    if edition.get("kind") == "typeset" and "डिजिटल संस्करण" not in label:
        return label + " — डिजिटल संस्करण"
    return label


def pdf_edition_picker(meta, *, reader_base="pdf/", file_base="", current_file=None):
    primary = meta.get("formats", {}).get("pdf")
    editions = meta.get("source", {}).get("pdf_editions") or []
    if not primary:
        return ""
    primary_edition = next((e for e in editions if e["file"] == primary), None)
    choices = [(primary, reader_base,
                edition_display_label(primary_edition) if primary_edition else "मूल पृष्ठ")]
    seen = {primary}
    for edition in editions:
        filename = edition["file"]
        if filename not in seen:
            choices.append((filename, reader_base + edition["id"] + "/",
                            edition_display_label(edition)))
            seen.add(filename)
    if len(choices) < 2:
        return ""
    current = next((c for c in choices if c[0] == current_file), choices[0])
    options, fallback = [], []
    for filename, reader, label in choices:
        direct = file_base + filename
        selected = " selected" if filename == current[0] else ""
        options.append(f'<option value="{esc(reader)}" data-download="{esc(direct)}"{selected}>{esc(label)}</option>')
        fallback.append(f'<li>{esc(label)}: <a href="{esc(reader)}">PDF हेर्नुहोस्</a> · '
                        f'<a href="{esc(direct)}" download>डाउनलोड</a></li>')
    return (
        '<div class="pdf-choice">'
        '<div class="pdf-choice-controls" hidden>'
        '<label>PDF संस्करण<select class="pdf-edition">' + "".join(options) + '</select></label>'
        '<div class="pdfacts">'
        f'<a class="pdfread pdf-choice-view" href="{esc(current[1])}">📖 PDF हेर्नुहोस्</a>'
        f'<a class="pdfread pdf-choice-download" href="{esc(file_base + current[0])}" download>⬇ PDF डाउनलोड</a>'
        '</div></div><ul class="pdf-choice-fallback">' + "".join(fallback) + '</ul></div>'
    )
