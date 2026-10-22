#!/usr/bin/env python3
"""Audit every built literary reader, chapter, and contents page.

Empty reader bodies and broken chapter structure fail CI. Short texts, repeated
headings and duplicate bodies are review signals, never automatic deletions.
"""
import argparse
from collections import defaultdict
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import unquote, urljoin, urlsplit

from sitegen.seo import page_url, read_head, valid_chapter_redirect
from sitegen.text import CHAPTER_RE, is_heading, text_blocks

VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
HEADINGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}


def normalize(value):
    return re.sub(r'\s+', ' ', value).strip()


class ReaderPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.readers = 0
        self.text = []
        self.body = []
        self.title = []
        self.headings = []
        self.toc = []
        self.navigation = {}
        self.anchor = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in VOID:
            if tag in {'br', 'hr'}:
                self.handle_data(' ')
            return
        self.stack.append((tag, attrs))
        if 'data-pagefind-body' in attrs:
            self.readers += 1
        if tag == 'h2' and self.in_reader():
            self.headings.append([])
        if tag == 'a':
            classes = attrs.get('class', '').split()
            if any(t == 'ol' and 'toc' in a.get('class', '').split() for t, a in self.stack):
                self.anchor = {'href': attrs.get('href', ''), 'text': ''}
                self.toc.append(self.anchor)
            if any(t == 'nav' and 'seqnav' in a.get('class', '').split() for t, a in self.stack):
                for direction in ('pv', 'nx'):
                    if direction in classes:
                        self.navigation[direction] = attrs.get('href', '')

    def handle_endtag(self, tag):
        if tag == 'a':
            self.anchor = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break
        if tag in {'div', 'p', 'h2'}:
            self.text.append(' ')
            self.body.append(' ')

    def in_reader(self):
        return any('data-pagefind-body' in attrs for _, attrs in self.stack)

    def handle_data(self, data):
        if self.anchor is not None:
            self.anchor['text'] += data
        if any(tag == 'h1' for tag, _ in self.stack):
            self.title.append(data)
        if not self.in_reader() or any(tag in {'script', 'style'} for tag, _ in self.stack):
            return
        self.text.append(data)
        if not any(tag in HEADINGS for tag, _ in self.stack):
            self.body.append(data)
        elif self.headings and any(tag == 'h2' for tag, _ in self.stack):
            self.headings[-1].append(data)


def audit_readers(site, sources=None):
    site = Path(site)
    errors, review = [], []
    documents, chapters, redirects = {}, {}, []
    fingerprints = defaultdict(list)
    reader_count = 0
    for path in sorted((site / 'authors').rglob('index.html')):
        rel = path.relative_to(site).as_posix()
        parts = path.relative_to(site).parts
        is_chapter = len(parts) == 5 and parts[-2].isdigit()
        is_work = len(parts) == 4
        head = read_head(path)
        if head.chapter_redirect:
            if not valid_chapter_redirect(site, path, head):
                errors.append(f'{rel}: invalid chapter redirect')
            redirects.append(rel)
            continue
        if head.noindex:
            if is_work or is_chapter:
                errors.append(f'{rel}: literary reader unexpectedly marked noindex')
            continue
        doc = ReaderPage()
        doc.feed(path.read_text(encoding='utf-8'))
        documents[path] = doc
        if is_chapter:
            chapters[path] = doc
            if doc.readers != 1:
                errors.append(f'{rel}: chapter needs exactly one literary body')
        if is_work and not doc.toc and doc.readers != 1:
            errors.append(f'{rel}: work needs a literary body or chapter contents')
        if not doc.readers:
            continue
        reader_count += 1
        text = normalize(''.join(doc.text))
        body = normalize(''.join(doc.body))
        if not any(c.isalpha() for c in text):
            errors.append(f'{rel}: empty literary body')
        elif not any(c.isalpha() for c in body):
            message = f'{rel}: heading-only literary body'
            (errors if is_chapter else review).append(message)
        elif len(body.split()) < 20:
            review.append(f'{rel}: short text ({len(body.split())} words); review against source')
        headings = [normalize(''.join(doc.title))] + [normalize(''.join(h)) for h in doc.headings]
        if len(headings) != len(set(headings)):
            review.append(f'{rel}: repeated heading; review source structure')
        if len(text.split()) >= 20:
            fingerprint = hashlib.sha256(text.encode()).hexdigest()
            fingerprints[fingerprint].append(rel)

    linked_chapters = set()
    for path, doc in documents.items():
        if not doc.toc:
            continue
        rel = path.relative_to(site).as_posix()
        routes = []
        for entry in doc.toc:
            target_url = urljoin(page_url(site, path), entry['href'])
            target = site / unquote(urlsplit(target_url).path).strip('/') / 'index.html'
            if urlsplit(target_url).netloc != urlsplit(page_url(site, path)).netloc:
                errors.append(f'{rel}: contents link leaves this archive: {entry["href"]}')
                continue
            if target not in chapters:
                errors.append(f'{rel}: contents link does not target an indexable chapter: {entry["href"]}')
                continue
            if target.parent.parent != path.parent:
                errors.append(f'{rel}: contents link targets a different work')
            if normalize(entry['text']) != normalize(''.join(chapters[target].title)):
                errors.append(f'{rel}: contents title differs from chapter heading: {entry["href"]}')
            routes.append(target)
            linked_chapters.add(target)
        if len(routes) != len(set(routes)):
            errors.append(f'{rel}: duplicate contents links')
        for index, target in enumerate(routes):
            expected = {'pv': routes[index - 1] if index else path}
            if index + 1 < len(routes):
                expected['nx'] = routes[index + 1]
            for direction in ('pv', 'nx'):
                href = chapters[target].navigation.get(direction)
                actual = None
                if href:
                    url = urljoin(page_url(site, target), href)
                    if urlsplit(url).netloc == urlsplit(page_url(site, target)).netloc:
                        actual = site / unquote(urlsplit(url).path).strip('/') / 'index.html'
                if actual != expected.get(direction):
                    errors.append(f'{target.relative_to(site)}: incorrect {direction} chapter navigation')
    for path in chapters.keys() - linked_chapters:
        errors.append(f'{path.relative_to(site)}: chapter missing from work contents')
    duplicates = [paths for paths in fingerprints.values() if len(paths) > 1]
    for paths in duplicates:
        review.append('Duplicate literary body (review, do not auto-delete): ' + ', '.join(paths))
    source_counts = {'source_works': 0, 'source_body_blocks': 0}
    if sources is not None:
        source_errors, source_counts = audit_source_text(site, Path(sources), documents)
        errors.extend(source_errors)
    return errors, {
        **source_counts,
        'reader_pages': reader_count, 'chapter_pages': len(chapters),
        'redirect_pages': len(redirects), 'duplicate_body_groups': duplicates,
        'review': review,
    }


def compact(value):
    # Rendering may collapse spaces or insert nonbreaking spaces before danda.
    return re.sub(r'\s+', '', unicodedata.normalize('NFC', value))


def audit_source_text(site, sources, documents):
    """Check source blocks against independently parsed HTML, in reading order.

    Promoted/merged headings need to remain present, but may move into the page
    title or be represented once. All other blocks must occur in source order,
    including repeated stanzas. This checks generation, not transcription quality.
    """
    errors = []
    counts = {'source_works': 0, 'source_body_blocks': 0}
    metadata_paths = sorted((sources / 'authors').glob('*/*/metadata.json'))
    if not metadata_paths:
        errors.append('Source audit: no work metadata found')
    for meta in metadata_paths:
        relative = meta.parent.relative_to(sources)
        path = site / relative / 'index.html'
        doc = documents.get(path)
        if doc is None:
            errors.append(f'{relative}: source work has no indexable reader')
            continue
        text_path = meta.with_name('text.txt')
        if not text_path.is_file():
            errors.append(f'{relative}: source text missing')
            continue
        counts['source_works'] += 1
        pages = [doc]
        if doc.toc:
            pages = []
            for entry in doc.toc:
                url = urljoin(page_url(site, path), entry['href'])
                chapter = documents.get(site / unquote(urlsplit(url).path).strip('/') / 'index.html')
                if chapter is not None:
                    pages.append(chapter)
        # Chapter subtitles are joined with an em dash in h1. Restore their
        # source separator for comparison, without changing literary body text.
        rendered = compact('\n'.join(
            (''.join(page.title).replace(' — ', '\n') + '\n' if doc.toc else '')
            + ''.join(page.text) for page in pages))
        cursor = 0
        for index, block in enumerate(text_blocks(text_path.read_text(encoding='utf-8')), 1):
            first = block.split('\n', 1)[0].strip()
            heading = is_heading(block) or (
                len(block.splitlines()) <= 2 and is_heading(first)
                and CHAPTER_RE.search(first))
            needle = compact(block)
            if heading:
                if needle not in rendered:
                    errors.append(f'{relative}: source heading block {index} missing from reader')
                continue
            counts['source_body_blocks'] += 1
            found = rendered.find(needle, cursor)
            if found < 0:
                errors.append(f'{relative}: source body block {index} missing or out of order')
            else:
                cursor = found + len(needle)
    return errors, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('site', type=Path)
    parser.add_argument('--sources', type=Path, help='Compare every source work with its rendered text')
    parser.add_argument('--report', type=Path, help='Write audit evidence as JSON')
    args = parser.parse_args()
    if not (args.site / 'index.html').is_file():
        parser.error('site must contain a built index.html')
    errors, report = audit_readers(args.site, args.sources)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({'errors': errors, **report}, ensure_ascii=False, indent=2) + '\n')
    for message in errors:
        print('ERROR:', message)
    for message in report['review']:
        print('REVIEW:', message)
    print(f"Reader audit: {report['reader_pages']} readers, {report['chapter_pages']} chapters, "
          f"{report['redirect_pages']} redirects, {len(errors)} errors, {len(report['review'])} review signals")
    if args.sources:
        print(f"Source audit: {report['source_works']} works, {report['source_body_blocks']} body blocks checked")
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
