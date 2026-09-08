#!/usr/bin/env python3
"""Faithful extraction of reviewed literary XHTML, including prose and notes.

No authorship decisions are inferred here. Callers must review the document and
explicitly approve notes before extraction. Unsupported structure stops the work.
"""
from __future__ import annotations
import copy
from dataclasses import dataclass
import re
import xml.etree.ElementTree as ET
from sahityaras_ingest import SourceError, ascii_space, classes, tag, xml


@dataclass
class LiteraryText:
    title: str
    text: str
    capture: bytes
    note_count: int
    continuation_count: int


def compact(value: str) -> str:
    return re.sub(r'[ \t\r\n\u2003]', '', value)


def extract_document(data: bytes, *, notes_approved: bool = False,
                     remove_ids: tuple[str, ...] = (), remove_links: tuple[str, ...] = (),
                     fallback_title: str = '', replacements: tuple[dict, ...] = ()) -> LiteraryText:
    tree = xml(data)
    body = next((n for n in tree.iter() if tag(n) == 'body'), None)
    if body is None:
        raise SourceError('Missing source body')
    body = copy.deepcopy(body)
    def remove_node(parent, node):
        siblings = list(parent)
        index = siblings.index(node)
        if index:
            previous = siblings[index-1]
            previous.tail = (previous.tail or '') + (node.tail or '')
        else:
            parent.text = (parent.text or '') + (node.tail or '')
        parent.remove(node)

    for identifier in remove_ids:
        matches = [(parent, node) for parent in body.iter() for node in parent
                   if node.get('id') == identifier]
        if len(matches) != 1:
            raise SourceError('Reviewed exclusion ID missing or ambiguous: ' + identifier)
        parent, node = matches[0]
        remove_node(parent, node)
    for href in remove_links:
        matches = [(parent, node) for parent in body.iter() for node in parent
                   if tag(node) == 'a' and node.get('href') == href]
        if len(matches) != 1:
            raise SourceError('Reviewed link exclusion missing or ambiguous')
        remove_node(*matches[0])
    for change in replacements:
        old, new = change['old'], change['new']
        if not old or not change.get('reason'):
            raise SourceError('Unexplained source repair')
        slots = [(node, field) for node in body.iter() for field in ('text','tail')
                 if old in (getattr(node,field) or '')]
        if sum((getattr(node,field) or '').count(old) for node,field in slots) != 1:
            raise SourceError('Source repair no longer matches exactly once')
        node, field = slots[0]
        setattr(node,field,getattr(node,field).replace(old,new))
    allowed = {'body', 'div', 'span', 'p', 'br', 'b', 'i', 'em', 'strong', 'sup',
               'sub', 'a', 'blockquote', 'ol', 'ul', 'li', 'hr', 'h1', 'h2', 'h3',
               'h4', 'small', 'u', 'section', 'article'}
    for node in body.iter():
        if tag(node) not in allowed:
            raise SourceError('Unsupported literary element: ' + tag(node))
        if any(k.lower().startswith('on') for k in node.attrib):
            raise SourceError('Executable source attribute')
    titles = [n for n in body.iter() if 'chapter-title' in classes(n)]
    title_node = titles[0] if titles else None
    title = ascii_space(''.join(title_node.itertext())).strip(' ') if title_node is not None else fallback_title
    if not title:
        raise SourceError('Missing reviewed title')
    parents = {child: parent for parent in body.iter() for child in parent}
    note_nodes = []
    for node in body.iter():
        if node.get('id', '').startswith('cite_note'):
            note_nodes.append(node)
    references = [n for n in body.iter() if 'reference' in classes(n)]
    if (note_nodes or references) and not notes_approved:
        raise SourceError('Notes require attribution review')
    labels = {}
    note_ids = {n.get('id') for n in note_nodes}
    for reference in references:
        anchors = [n for n in reference.iter() if tag(n) == 'a']
        if len(anchors) != 1 or not anchors[0].get('href', '').startswith('#'):
            raise SourceError('Nonlocal or ambiguous note reference')
        target = anchors[0].get('href')[1:]
        if target not in note_ids:
            raise SourceError('Note target missing: ' + target)
        labels.setdefault(target, ascii_space(''.join(reference.itertext())).strip(' '))
    # Empty note wrappers are harmless, but text must belong to an identified note.
    for node in body.iter():
        if classes(node) & {'references', 'mw-references-wrap'}:
            for n in node.iter():
                if n is node or n in note_nodes:
                    continue
                ancestor = n
                while ancestor is not node and ancestor not in note_nodes:
                    ancestor = parents.get(ancestor, node)
                if ancestor not in note_nodes and (n.text or '').strip():
                    raise SourceError('Unidentified note text')
    for node in body.iter():
        if tag(node) == 'a' and node.get('href'):
            ancestor = node
            while ancestor is not body and ancestor not in references and ancestor not in note_nodes:
                ancestor = parents.get(ancestor, body)
            if ancestor is body:
                raise SourceError('Literary link requires review: ' + node.get('href'))
    continuation_count = 0
    skip = set(note_nodes)
    if title_node is not None:
        skip.add(title_node)

    def inline(node):
        if 'mw-cite-backlink' in classes(node):
            return ''
        if tag(node) == 'br':
            return '\n'
        prefix = ''
        style = node.get('style', '')
        if 'mw-poem-indented' in classes(node):
            match = re.search(r'margin-inline-start\s*:\s*([0-9]+)em', style)
            if not match or not 0 < int(match[1]) <= 24:
                raise SourceError('Unknown poem indentation')
            prefix = '\u2003' * int(match[1])
        elif re.search(r'(?:margin-(?:inline-start|left)|padding-left)\s*:', style):
            # Auto-centering blocks is layout, not line indentation.
            if not re.search(r'margin-left\s*:\s*auto', style):
                raise SourceError('Unrecognized source indentation: ' + style)
        if tag(node) in {'div','blockquote'}:
            return '\n\n' + ascii_space(node.text) + ''.join(inline(c)+ascii_space(c.tail) for c in node) + '\n\n'
        if tag(node) not in {'p', 'span', 'b', 'i', 'em', 'strong', 'sup', 'sub',
                             'a', 'small', 'u', 'li', 'h1', 'h2', 'h3', 'h4'}:
            raise SourceError('Unexpected inline structure: ' + tag(node))
        return prefix + ascii_space(node.text) + ''.join(inline(c) + ascii_space(c.tail) for c in node)

    def render(start, excluded):
        nonlocal continuation_count
        chunks = []
        continuation = False
        def append(value):
            nonlocal continuation
            value = '\n'.join(line.strip(' \t\r') for line in value.split('\n')).strip('\n')
            if not value.strip():
                return
            if continuation:
                if not chunks:
                    raise SourceError('Continuation without preceding text')
                chunks[-1] += '\n' + value
                continuation = False
            else:
                chunks.append(value)
        def walk(node):
            nonlocal continuation, continuation_count
            if node in excluded or 'mw-cite-backlink' in classes(node):
                return
            if classes(node) & {'references', 'mw-references-wrap'}:
                return
            style = re.sub(r'\s+', '', node.get('style', ''))
            if 'margin-top:-1lh' in style:
                if (node.text or '').strip() or continuation:
                    raise SourceError('Unexpected continuation marker')
                continuation = True
                continuation_count += 1
                for child in node:
                    walk(child)
                    if (child.tail or '').strip():
                        append(ascii_space(child.tail))
                return
            if tag(node) in {'p', 'h1', 'h2', 'h3', 'h4', 'li'} or 'chapter-title' in classes(node):
                # chapter-title is a div; process its inline children explicitly.
                if tag(node) == 'div':
                    append(ascii_space(node.text) + ''.join(inline(c)+ascii_space(c.tail) for c in node))
                else:
                    append(inline(node))
                return
            if tag(node) == 'hr':
                if (node.text or '').strip():
                    raise SourceError('Text within rule')
                return
            if tag(node) in {'span','b','i','em','strong','small','a','sup','sub'} and not any(tag(n) in {'div','p','blockquote'} for n in node.iter() if n is not node):
                if ''.join(node.itertext()).strip():
                    append(inline(node))
                return
            if (node.text or '').strip():
                append(ascii_space(node.text))
            for child in node:
                walk(child)
                if (child.tail or '').strip():
                    append(ascii_space(child.tail))
        walk(start)
        if continuation:
            raise SourceError('Unpaired final continuation')
        result = '\n\n'.join(chunks)
        def expected(n):
            if n in excluded or 'mw-cite-backlink' in classes(n):
                return ''
            if classes(n) & {'references','mw-references-wrap'}:
                return ''
            return (n.text or '') + ''.join(expected(c) + (c.tail or '') for c in n)
        if compact(expected(start)) != compact(result):
            raise SourceError('Source text conservation failed')
        return result
    text = render(body, skip)
    for note in note_nodes:
        # Notes may have direct text/br children or block paragraphs.
        copied = copy.deepcopy(note)
        copied.tag = 'p' if not any(tag(n) in {'p','div'} for n in copied) else 'div'
        content = render(copied, set())
        label = labels.get(note.get('id'), '')
        text += '\n\n' + (label + ' ' if label else '') + content
    if not text.strip():
        raise SourceError('Empty literary text')
    ns = '{http://www.w3.org/1999/xhtml}'
    ET.register_namespace('', ns[1:-1])
    capture = ET.Element(ns+'html', {'lang':'ne'})
    head = ET.SubElement(capture, ns+'head')
    ET.SubElement(head, ns+'meta', {'charset':'utf-8'})
    ET.SubElement(head, ns+'title').text = title
    capture.append(body)
    return LiteraryText(title, text+'\n', ET.tostring(capture,encoding='utf-8',xml_declaration=True)+b'\n',len(note_nodes),continuation_count)
