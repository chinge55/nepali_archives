"""Faithful literary-text rendering and long-work pagination."""

import html
import re


def esc(value: str | None) -> str:
    return html.escape(value or "")


def is_heading(block: str) -> bool:
    """Recognize a printed section heading without inventing structure."""
    if "\n" in block or len(block) > 40:
        return False
    text = block.strip()
    marker = re.fullmatch(r"\(([ऀ-ॿ])\)", text)
    if marker and not marker.group(1).isdigit():
        return True
    if not text or text[0] in "0123456789०१२३४५६७८९([‘’“”\"":
        return False
    if text[-1] in "।॥!?,.;:—–…‘’“”":
        return False
    letters = len(re.findall(r"[ऀ-ॿ]", text))
    return letters >= 3 and (" " in text or letters >= 4)


_COLOPHON_RE = re.compile(r"^\s*(वि|बि)\.?\s*सं\.?\s*[०-९]")
_NBSP_PUNCT = re.compile(r" ([।॥!?])")
CHAPTER_RE = re.compile(
    r"काण्ड|सर्ग|सगैँ|अध्याय|विश्राम|विश्वाम|परिच्छेद|अङ्क|उल्लास|खण्ड|"
    r"सोपान|परिशिष्ट|विचार"
)
DEVNUM = str.maketrans("0123456789", "०१२३४५६७८९")


def devnum(value: object) -> str:
    return str(value).translate(DEVNUM)


def _no_break_punctuation(value: str) -> str:
    return _NBSP_PUNCT.sub(" \\1", value)


def work_html(text: str, verse: bool) -> str:
    """Render source blocks without modernizing or filling missing text."""
    blocks = [
        block.strip("\n")
        for block in text.replace("\r\n", "\n").split("\n\n")
    ]
    output = []
    for block in blocks:
        if not block.strip():
            continue
        if _COLOPHON_RE.match(block):
            line = re.sub(r"\s+", " ", block.replace("\n", " ")).strip()
            output.append(f'<p class="colophon">{esc(line)}</p>')
        elif is_heading(block):
            output.append(f'<h2 class="sec">{esc(block)}</h2>')
        elif verse:
            lines = block.split("\n")
            if len(lines) > 1 and re.fullmatch(
                r"[०-९0-9]{1,4}", lines[0].strip()
            ):
                output.append(
                    '<div class="stanza snum"><span class="ln">'
                    f"{esc(lines[0].strip())}</span></div>"
                )
                lines = lines[1:]
            rendered_lines = "".join(
                f'<span class="ln">{_no_break_punctuation(esc(line))}</span>'
                for line in lines
            )
            css_class = (
                "stanza snum"
                if re.fullmatch(r"[०-९0-9]{1,4}", block.strip())
                else "stanza"
            )
            output.append(f'<div class="{css_class}">{rendered_lines}</div>')
        else:
            paragraph = _no_break_punctuation(esc(block).replace("\n", " "))
            output.append(f'<p class="stanza">{paragraph}</p>')
    return "\n".join(output)


def paginate_work(
    text: str, balance: bool = False
) -> list[tuple[str, str]] | None:
    """Split a long work only at printed sections, or balance huge unsectioned text."""
    blocks = [
        block.strip("\n")
        for block in text.replace("\r\n", "\n").split("\n\n")
        if block.strip()
    ]

    def is_chapter(block: str) -> bool:
        first = block.split("\n", 1)[0].strip()
        return (
            len(block.splitlines()) <= 2
            and is_heading(first)
            and not re.match(r"^इति(?:\s|$)", first)
            and bool(CHAPTER_RE.search(first))
        )

    indexes = [index for index, block in enumerate(blocks) if is_chapter(block)]
    if len(indexes) >= 2 and len(text) > 8000:
        front = blocks[: indexes[0]]
        bounds = indexes + [len(blocks)]
        pages: list[tuple[str, str]] = []
        if (
            front
            and len("\n\n".join(front)) > 400
            and is_heading(front[0].split("\n", 1)[0].strip())
        ):
            pages.append(
                (front[0].split("\n", 1)[0].strip(), "\n\n".join(front[1:]))
            )
            front = []
        for page_index, start in enumerate(indexes):
            body_blocks = blocks[start + 1 : bounds[page_index + 1]]
            if page_index == 0 and front:
                body_blocks = front + body_blocks
            pages.append(
                (
                    blocks[start].replace("\n", " — "),
                    "\n\n".join(body_blocks),
                )
            )
        return pages
    if balance:
        target = 20000
        pages = []
        current: list[str] = []
        size = 0
        number = 1
        for block in blocks:
            current.append(block)
            size += len(block)
            if size >= target:
                pages.append((f"भाग {devnum(number)}", "\n\n".join(current)))
                current, size, number = [], 0, number + 1
        if current:
            pages.append((f"भाग {devnum(number)}", "\n\n".join(current)))
        return pages if len(pages) >= 2 else None
    return None
