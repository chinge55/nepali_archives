#!/usr/bin/env python3
"""Offline EPUB-source inspection and faithful verse extraction for Sahitya Ras.

First-pilot scope: simple XHTML poems, explicit stanza breaks, indentation and
page-continuation markers. Notes and unfamiliar structures fail for review.
This tool does not fetch sources, modernize text, or overwrite archive works.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET


class SourceError(ValueError):
    """A source cannot be extracted safely by this adapter."""


def tag(node: ET.Element) -> str:
    return node.tag.rsplit('}', 1)[-1]


def classes(node: ET.Element) -> set[str]:
    return set(node.get('class', '').split())


def xml(data: bytes) -> ET.Element:
    if re.search(br'<!ENTITY|<!DOCTYPE[^>]*(?:SYSTEM|PUBLIC|\[)', data, re.I):
        raise SourceError('External entities and document type subsets are unsupported')
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise SourceError(f'Invalid source XML: {exc}') from exc


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def package_path(root: Path, base: Path, href: str) -> Path:
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise SourceError(f'Expected a local package file: {href}')
    decoded = unquote(parsed.path)
    if not decoded or '\\' in decoded or decoded.startswith('/'):
        raise SourceError(f'Invalid package path: {href}')
    target = (base / decoded).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise SourceError(f'Missing file or path outside package: {href}')
    return target


def inventory(root: Path) -> dict:
    """Read the container and spine; include all non-spine XHTML as well."""
    root = root.resolve()
    container = xml((root / 'META-INF/container.xml').read_bytes())
    paths = [n.get('full-path') for n in container.iter() if tag(n) == 'rootfile']
    if len(paths) != 1 or not paths[0]:
        raise SourceError('Expected one EPUB package document')
    opf_path = package_path(root, root, paths[0])
    opf = xml(opf_path.read_bytes())
    items = {}
    for item in opf.iter():
        if tag(item) != 'item':
            continue
        identifier = item.get('id')
        if not identifier or identifier in items:
            raise SourceError('Missing or duplicate manifest ID')
        items[identifier] = item
    spine = [n.get('idref') for n in opf.iter() if tag(n) == 'itemref']
    if not spine or len(spine) != len(set(spine)):
        raise SourceError('Missing or duplicate spine entries')
    if any(identifier not in items for identifier in spine):
        raise SourceError('Spine references a missing manifest entry')
    records = []
    for identifier in spine + [key for key in items if key not in spine]:
        item = items[identifier]
        if item.get('media-type') != 'application/xhtml+xml':
            if identifier in spine:
                raise SourceError('Non-XHTML spine entry needs review')
            continue
        path = package_path(root, opf_path.parent, item.get('href', ''))
        data = path.read_bytes()
        document = xml(data)
        titles = [n for n in document.iter() if tag(n) == 'title']
        records.append({
            'path': path.relative_to(root).as_posix(),
            'manifest_id': identifier,
            'spine_position': spine.index(identifier) + 1 if identifier in spine else None,
            'title': ''.join(titles[0].itertext()).strip() if titles else '',
            'sha256': digest(data),
        })
    declared = {record['path'] for record in records}
    undeclared = sorted(p.relative_to(root).as_posix() for p in root.rglob('*.xhtml')
                        if p.relative_to(root).as_posix() not in declared)
    if undeclared:
        raise SourceError('Unmanifested XHTML requires review: ' + ', '.join(undeclared))
    return {'package_document': opf_path.relative_to(root).as_posix(),
            'package_sha256': digest(opf_path.read_bytes()), 'documents': records}


def ascii_space(value: str | None) -> str:
    return re.sub(r'[ \t\r\n]+', ' ', value or '')


@dataclass(frozen=True)
class ExtractedPoem:
    title: str
    head_title: str
    text: str
    source_sha256: str
    continuation_markers: int
    indented_lines: int
    blocks: int


def extract_poem(data: bytes) -> ExtractedPoem:
    document = xml(data)
    containers = [n for n in document.iter() if 'prp-pages-output' in classes(n)]
    if len(containers) != 1:
        raise SourceError('Expected exactly one prp-pages-output literary container')
    container = containers[0]
    allowed = {'div', 'span', 'p', 'br', 'b', 'i', 'em', 'strong'}
    for node in container.iter():
        if tag(node) not in allowed:
            raise SourceError(f'Unsupported literary element: {tag(node)}')
        if any(k.rsplit('}', 1)[-1].lower().startswith('on') for k in node.attrib):
            raise SourceError('Executable attribute in literary content')
        if classes(node) & {'reference', 'references', 'reflist'}:
            raise SourceError('Notes require a separate attribution and extraction review')
        if any('note' in v for k, v in node.attrib.items() if k.endswith('}type')):
            raise SourceError('Notes require a separate attribution and extraction review')
    titles = [n for n in container.iter() if 'chapter-title' in classes(n)]
    if len(titles) != 1:
        raise SourceError('Expected exactly one visible work title')
    title_node = titles[0]
    title = ascii_space(''.join(title_node.itertext())).strip(' ')
    head = next((n for n in document.iter() if tag(n) == 'title'), None)
    head_title = ascii_space(''.join(head.itertext())).strip(' ') if head is not None else ''
    paragraphs: list[tuple[str, bool]] = []
    continuation = False
    continuation_count = 0
    indents = 0

    def inline(node: ET.Element) -> str:
        nonlocal indents
        if tag(node) == 'br':
            if list(node) or (node.text or '').strip():
                raise SourceError('Unexpected content inside line break')
            return '\n'
        if tag(node) not in {'p', 'span', 'b', 'i', 'em', 'strong'}:
            raise SourceError(f'Unsupported inline element: {tag(node)}')
        prefix = ''
        style = node.get('style', '')
        if 'mw-poem-indented' in classes(node):
            match = re.search(r'margin-inline-start\s*:\s*([0-9]+)em\s*;', style)
            if not match or not 0 < int(match[1]) <= 12:
                raise SourceError('Unrecognized source indentation')
            prefix = '\u2003' * int(match[1])
            indents += 1
        elif re.search(r'margin-(?:inline-start|left)|padding-left|text-indent', style):
            raise SourceError('Unrecognized inline indentation')
        out = prefix + ascii_space(node.text)
        for child in node:
            out += inline(child) + ascii_space(child.tail)
        return out

    def walk(node: ET.Element):
        nonlocal continuation, continuation_count
        if node is title_node:
            return
        style = re.sub(r'\s+', '', node.get('style', ''))
        if 'margin-top:' in style:
            if style != 'margin-top:-1lh;' or list(node) or (node.text or '').strip():
                raise SourceError('Unknown page-continuation layout')
            if not paragraphs or continuation:
                raise SourceError('Unpaired page-continuation marker')
            continuation = True
            continuation_count += 1
            return
        if tag(node) == 'p':
            text = inline(node)
            lines = [line.strip(' \t\r') for line in text.split('\n')]
            text = '\n'.join(lines).strip('\n')
            if text.strip():
                paragraphs.append((text, continuation))
                continuation = False
            return
        if (node.text or '').strip():
            raise SourceError('Unclassified text outside paragraph')
        for child in node:
            walk(child)
            if (child.tail or '').strip():
                raise SourceError('Unclassified trailing text outside paragraph')

    walk(container)
    if continuation:
        raise SourceError('Page-continuation marker has no following paragraph')
    if not paragraphs:
        raise SourceError('Empty literary text')
    output = ''
    for text, joins_previous in paragraphs:
        output += ('\n' if joins_previous else '\n\n') if output else ''
        output += text
    output += '\n'
    # Only HTML formatting whitespace and our explicit em-space layout may vary.
    def letters(value):
        return re.sub(r'[ \t\r\n\u2003]', '', value)
    source_text = ''.join(container.itertext())
    source_title = ''.join(title_node.itertext())
    if letters(source_text) != letters(source_title + output):
        raise SourceError('Text conservation check failed')
    return ExtractedPoem(title, head_title, output, digest(data), continuation_count,
                         indents, len(output.rstrip('\n').split('\n\n')))


def source_capture(data: bytes, title: str) -> bytes:
    """Keep the included literary container, without external site resources."""
    # Validation intentionally fails before publishing unfamiliar mixed content.
    extract_poem(data)
    document = xml(data)
    container = next(n for n in document.iter() if 'prp-pages-output' in classes(n))
    ET.register_namespace('', 'http://www.w3.org/1999/xhtml')
    ns = '{http://www.w3.org/1999/xhtml}'
    html = ET.Element(ns + 'html', {'lang': 'ne'})
    head = ET.SubElement(html, ns + 'head')
    ET.SubElement(head, ns + 'meta', {'charset': 'utf-8'})
    ET.SubElement(head, ns + 'title').text = title
    body = ET.SubElement(html, ns + 'body')
    body.append(container)
    return ET.tostring(html, encoding='utf-8', xml_declaration=True) + b'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    inv = sub.add_parser('inventory')
    inv.add_argument('package', type=Path, help='Extracted EPUB source directory containing META-INF')
    ext = sub.add_parser('extract')
    ext.add_argument('source', type=Path)
    ext.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'inventory':
            result = inventory(args.package)
        else:
            poem = extract_poem(args.source.read_bytes())
            result = asdict(poem)
            if args.output:
                if args.output.exists():
                    if args.output.read_text(encoding='utf-8') != poem.text:
                        raise SourceError('Refusing to overwrite a different existing output')
                else:
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    args.output.write_text(poem.text, encoding='utf-8')
                result.pop('text')
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (SourceError, OSError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
