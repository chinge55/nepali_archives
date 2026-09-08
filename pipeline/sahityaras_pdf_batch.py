#!/usr/bin/env python3
"""Stage or apply a reviewed Sahitya Ras PDF page manifest.

The manifest pins original downloads, every page disposition, per-work slices,
editorial redactions, existing text/metadata baselines, and output hashes.
PDF dependencies are only needed for this optional ingestion step, never builds.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import tempfile

from sahityaras_pdfs import slice_pdf

ROOT = Path(__file__).resolve().parent.parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9_-]+', value):
        raise ValueError('Invalid identifier')
    return value


def filename(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9_-]+\.pdf', value):
        raise ValueError('Invalid PDF filename')
    return value


def literary_documents(book):
    """Expand reviewed members of a shared-page anthology document."""
    result = []
    for document in book['documents']:
        if document['decision'] == 'split':
            for member in document['members']:
                result.append({**member, 'path': document['path'] + '#' + member['id']})
        else:
            result.append(document)
    return result


def page_redactions(book, document, number):
    return (book.get('redactions', {}).get(str(number), [])
            + document.get('redactions', {}).get(str(number), []))


def validate_manifest(manifest):
    if manifest.get('schema_version') != 1 or not manifest.get('reviewed'):
        raise ValueError('Expected a reviewed PDF manifest')
    books = {}
    assigned = set()
    for book in manifest['books']:
        bid = identifier(book['id'])
        if bid in books:
            raise ValueError('Duplicate source book')
        books[bid] = book
        next_page = 1
        seen = set()
        for doc in book['documents']:
            if doc['path'] in seen:
                raise ValueError('Duplicate source document')
            seen.add(doc['path'])
            exclusions = doc.get('excluded_pages', [])
            excluded_numbers = [item['page'] for item in exclusions]
            if len(set(excluded_numbers)) != len(excluded_numbers) or any(
                isinstance(n, bool) or not isinstance(n, int) or not doc['page_start'] <= n <= doc['page_end']
                for n in excluded_numbers
            ) or any(not item.get('reason') for item in exclusions):
                raise ValueError('Invalid editorial-page exclusion')
            if doc['page_start'] != next_page or doc['page_end'] < next_page:
                raise ValueError('Source page accounting has a gap or overlap')
            next_page = doc['page_end'] + 1
            if doc['decision'] not in {'include', 'map-existing', 'exclude', 'defer', 'split'} or not doc.get('reason'):
                raise ValueError('Missing source page disposition')
            if doc['decision'] == 'split':
                members = doc.get('members', [])
                member_ids = [identifier(m['id']) for m in members]
                if not members or len(set(member_ids)) != len(member_ids):
                    raise ValueError('Missing or duplicate split members')
                for member in members:
                    if not doc['page_start'] <= member['page_start'] <= member['page_end'] <= doc['page_end']:
                        raise ValueError('Member outside source document')
                    if member.get('decision') not in {'include', 'map-existing'} or not member.get('reason'):
                        raise ValueError('Unreviewed split member')
        for doc in literary_documents(book):
            if doc['decision'] in {'include', 'map-existing'}:
                if not doc.get('destination'):
                    raise ValueError('Included document has no destination')
                assigned.add((bid, doc['path'], doc['destination']))
        if next_page != book['page_count'] + 1:
            raise ValueError('Source page accounting incomplete')
    actual = set()
    destinations = set()
    for work in manifest['works']:
        dest = f"archives/authors/{identifier(work['author_id'])}/{identifier(work['id'])}"
        if dest in destinations:
            raise ValueError('Duplicate work destination')
        destinations.add(dest)
        before = work['metadata_before']
        if before['author']['id'] != work['author_id'] or before['id'] != work['id']:
            raise ValueError('Work identity does not match baseline')
        if before['rights']['status'] not in {'public-domain', 'permission-granted'}:
            raise ValueError('Work outside publication gate')
        ids = set(); files = set()
        for edition in work['pdfs']:
            eid = identifier(edition['id']); fn = filename(edition['file'])
            if eid in ids or fn in files:
                raise ValueError('Duplicate PDF edition')
            ids.add(eid); files.add(fn)
            book = books[edition['book']]
            selected = []
            approved_redactions = {}
            for path in edition['documents']:
                doc = next(d for d in literary_documents(book) if d['path'] == path)
                key = (book['id'], path, dest)
                if key not in assigned or key in actual:
                    raise ValueError('Unapproved or duplicate document assignment')
                actual.add(key)
                excluded = {item['page'] for item in doc.get('excluded_pages', [])}
                retained = [n for n in range(doc['page_start'], doc['page_end'] + 1) if n not in excluded]
                selected.extend(retained)
                for number in retained:
                    approved_redactions[number] = page_redactions(book, doc, number)
            if selected != [p['page'] for p in edition['pages']]:
                raise ValueError('PDF selection differs from reviewed work boundaries')
            for page in edition['pages']:
                expected = approved_redactions[page['page']]
                if page.get('redactions', []) != expected:
                    raise ValueError('PDF does not apply the reviewed editorial redactions')
            for section in edition.get('sections', []):
                if not 1 <= section['page_start'] <= section['page_end'] <= len(selected):
                    raise ValueError('Section target outside sliced PDF')
    if actual != assigned:
        raise ValueError('Literary PDF assignments incomplete')
    return books


def metadata_for(work, books, date):
    result = deepcopy(work['metadata_before'])
    additions = []
    for pdf in work['pdfs']:
        book = books[pdf['book']]
        item = {'id': pdf['id'], 'file': pdf['file'], 'kind': book['kind'],
                'label': 'साहित्यरस · ' + book['title'], 'sha256': pdf['sha256'],
                'page_count': len(pdf['pages']),
                'origin': {'name': 'Sahitya Ras', 'url': book['pdf_url']}}
        if pdf.get('sections'):
            item['sections'] = pdf['sections']
        additions.append(item)
    old = result['source'].get('pdf_editions', [])
    if {p['id'] for p in old} & {p['id'] for p in additions}:
        raise ValueError('Edition already in baseline')
    result['source']['pdf_editions'] = old + additions
    if not result['formats'].get('pdf'):
        primary = additions[0]
        result['formats']['pdf'] = primary['file']
        result['source']['pdf'] = primary['file']
        result['pages'] = primary['page_count']
    result['updated'] = date
    return result


def build_outputs(manifest, originals, root, *, verify_hashes=True):
    books = validate_manifest(manifest)
    for book in books.values():
        source = originals / (book['id'] + '.pdf')
        if digest(source.read_bytes()) != book['sha256']:
            raise ValueError('Original PDF changed: ' + book['id'])
    outputs = {}
    for work in manifest['works']:
        relative = f"archives/authors/{work['author_id']}/{work['id']}"
        directory = root / relative
        if digest((directory / 'text.txt').read_bytes()) != work['text_sha256']:
            raise ValueError('Existing text changed: ' + work['id'])
        if digest(encoded(work['metadata_before'])) != work['baseline_metadata_sha256']:
            raise ValueError('Invalid metadata baseline')
        for pdf in work['pdfs']:
            data = slice_pdf(originals / (pdf['book'] + '.pdf'), pdf['pages'],
                             title=work['metadata_before']['title'],
                             author=work['metadata_before']['author']['name'])
            if verify_hashes and digest(data) != pdf['sha256']:
                raise ValueError('PDF differs from reviewed output: ' + pdf['file'])
            pdf['sha256'] = digest(data)
            outputs[relative + '/' + pdf['file']] = data
        data = encoded(metadata_for(work, books, manifest['prepared_date']))
        if verify_hashes and digest(data) != work['metadata_sha256']:
            raise ValueError('Metadata differs from reviewed output')
        work['metadata_sha256'] = digest(data)
        outputs[relative + '/metadata.json'] = data
    return outputs


def write_outputs(outputs, manifest, destination, *, apply=False):
    baselines = {f"archives/authors/{w['author_id']}/{w['id']}/metadata.json": w['baseline_metadata_sha256']
                 for w in manifest['works']}
    pending = []
    for relative, data in outputs.items():
        path = destination / relative
        if path.is_symlink() or not path.resolve().is_relative_to(destination.resolve()):
            raise ValueError('Unsafe output destination')
        if path.exists():
            previous = path.read_bytes()
            if previous == data:
                continue
            if not apply or digest(previous) != baselines.get(relative):
                raise ValueError('Refusing changed destination: ' + relative)
        pending.append((path, data))
    # Preflight every path before any write. Atomic per file, resumable on rerun.
    for path, data in pending:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.pdf-import-', delete=False) as handle:
            temp = Path(handle.name)
            handle.write(data)
        try:
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)
    return len(pending)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('originals', type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--stage', type=Path)
    mode.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.stage and args.stage.resolve().is_relative_to((ROOT / 'archives').resolve()):
        parser.error('Stage outside canonical archives')
    try:
        manifest = json.loads(args.manifest.read_text())
        outputs = build_outputs(manifest, args.originals, ROOT)
        count = write_outputs(outputs, manifest, ROOT if args.apply else args.stage.resolve(), apply=args.apply)
        print(f"{len(manifest['books'])} PDF books accounted for; {len(manifest['works'])} work destinations; {count} files written")
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
