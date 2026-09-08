#!/usr/bin/env python3
"""Stage or apply a reviewed, hash-pinned Sahitya Ras anthology manifest.

This first-batch materializer only adds independent poems and collection tags.
It does not replace existing transcriptions, discover works, or fetch sources.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import tempfile

from sahityaras_ingest import SourceError, digest, extract_poem, inventory, package_path, source_capture
from devanagari_slug import romanize

ROOT = Path(__file__).resolve().parent.parent


def encoded(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def add_collection(metadata: dict, collection: str) -> dict:
    result = json.loads(json.dumps(metadata))
    description = result.get('description') or ''
    match = re.match(r'From the collection ([^.]+)\.', description)
    if match:
        names = [name.strip() for name in match[1].split(';')]
        if collection not in names:
            names.append(collection)
        result['description'] = 'From the collection ' + '; '.join(names) + '.' + description[match.end():]
    else:
        result['description'] = f'From the collection {collection}.' + (' ' + description if description else '')
    return result


def poem_files(manifest: dict, entry: dict, data: bytes) -> dict[str, bytes]:
    """Prepare review drafts without requiring their output hashes yet."""
    poem = extract_poem(data)
    work_id = entry['work_id']
    author = manifest['author']
    metadata = {
        'id': work_id, 'title': poem.title,
        'title_roman': entry.get('title_roman') or romanize(poem.title).title(),
        'subtitle': entry.get('subtitle'), 'author': author,
        'language': 'ne', 'script': 'Devanagari', 'genre': ['kavita', 'poem'],
        'first_published': {'bs': None, 'ad': None},
        'edition': manifest['edition'], 'publisher': manifest['publisher'],
        'description': f"From the collection {manifest['collection']}. Transcribed from Sahitya Ras's edition; original spelling and source numbering preserved. Not checked against the printed pages.",
        'rights': manifest['rights'],
        'source': {'name': 'Sahitya Ras (sahityaras.com)', 'url': entry['source_url'],
                   'pdf': None, 'html': 'extracted/index.html'},
        'pages': None,
        'text': {'extraction_method': 'html', 'ocr_status': 'born-digital',
                 'proofread': False, 'quality': None},
        'formats': {'pdf': None, 'txt': 'text.txt', 'html': 'reader.html', 'epub': 'reader.epub'},
        'added': manifest['prepared_date'], 'updated': manifest['prepared_date'],
    }
    files = {'metadata.json': encoded(metadata), 'text.txt': poem.text.encode('utf-8'),
             'extracted/index.html': source_capture(data, poem.head_title)}
    return files


def plan_files(manifest: dict, package: Path, root: Path) -> dict[str, bytes]:
    if manifest.get('schema_version') != 1 or manifest.get('book_type') != 'collection':
        raise SourceError('Unsupported manifest version or book type')
    author = manifest['author']
    if not re.fullmatch(r'[a-z0-9_-]+', author['id']):
        raise SourceError('Invalid author ID')
    if manifest['rights']['status'] not in {'public-domain', 'permission-granted'}:
        raise SourceError('Work rights do not pass the publication gate')
    actual = inventory(package)
    expected = manifest['documents']
    paths = [entry['path'] for entry in expected]
    if len(paths) != len(set(paths)):
        raise SourceError('Duplicate document decisions')
    indexed = {entry['path']: entry for entry in actual['documents']}
    if set(paths) != set(indexed):
        raise SourceError('Manifest does not account for every package document')
    if manifest['source']['package_sha256'] != actual['package_sha256']:
        raise SourceError('Package reading order changed')
    outputs: dict[str, bytes] = {}
    destinations = set()
    for entry in expected:
        if entry['sha256'] != indexed[entry['path']]['sha256']:
            raise SourceError('Source changed: ' + entry['path'])
        if entry['spine_position'] != indexed[entry['path']]['spine_position']:
            raise SourceError('Reading-order decision mismatch')
        decision = entry['decision']
        if decision not in {'include', 'map-existing', 'exclude', 'defer'} or not entry.get('reason'):
            raise SourceError('Every document needs an explicit decision and reason')
        if decision in {'exclude', 'defer'}:
            continue
        if entry.get('review') != 'accepted':
            raise SourceError('Unreviewed output decision')
        work_id = entry['work_id']
        if not re.fullmatch(r'[a-z0-9_-]+', work_id) or work_id in destinations:
            raise SourceError('Invalid or duplicate work destination')
        destinations.add(work_id)
        relative = f"archives/authors/{author['id']}/{work_id}"
        destination = root / relative
        if not destination.resolve().is_relative_to(root.resolve()):
            raise SourceError('Destination escapes archive root')
        if decision == 'map-existing':
            metadata_path = destination / 'metadata.json'
            text_path = destination / 'text.txt'
            if digest(text_path.read_bytes()) != entry['baseline_text_sha256']:
                raise SourceError('Existing transcription changed; review again: ' + work_id)
            current = metadata_path.read_bytes()
            metadata = json.loads(current)
            if metadata['author'] != author:
                raise SourceError('Existing author identity does not match')
            updated = encoded(add_collection(metadata, manifest['collection']))
            if digest(current) != entry['baseline_metadata_sha256'] and current != updated:
                raise SourceError('Existing metadata changed; review again: ' + work_id)
            # A frozen expected output prevents changed metadata from being accepted
            # simply because it happens to already contain the collection name.
            if digest(updated) != entry['metadata_output_sha256']:
                raise SourceError('Existing metadata differs from reviewed output: ' + work_id)
            outputs[relative + '/metadata.json'] = updated
            continue
        source_path = package_path(package, package, entry['path'])
        data = source_path.read_bytes()
        poem = extract_poem(data)
        if poem.title != entry['title']:
            raise SourceError('Visible source title changed')
        files = poem_files(manifest, entry, data)
        for name, content in files.items():
            if digest(content) != entry['outputs'][name]:
                raise SourceError('Extraction differs from reviewed output: ' + entry['path'])
            outputs[relative + '/' + name] = content
    return outputs


def write_files(outputs: dict[str, bytes], root: Path, *, apply: bool, manifest: dict) -> int:
    """Preflight all destinations before writing; reruns leave equal files alone."""
    existing_metadata = {
        f"archives/authors/{manifest['author']['id']}/{entry['work_id']}/metadata.json": entry
        for entry in manifest['documents'] if entry['decision'] == 'map-existing'
    }
    pending = []
    for relative, data in outputs.items():
        path = root / relative
        if not path.resolve().is_relative_to(root.resolve()):
            raise SourceError('Output path escapes destination root')
        if path.exists():
            current = path.read_bytes()
            if current == data:
                continue
            allowed = existing_metadata.get(relative) if apply else None
            if not allowed or digest(current) != allowed['baseline_metadata_sha256']:
                raise SourceError('Refusing to overwrite changed output: ' + relative)
        pending.append((path, data))
    if apply:
        for entry in manifest['documents']:
            if entry['decision'] != 'include':
                continue
            directory = root / 'archives/authors' / manifest['author']['id'] / entry['work_id']
            if directory.exists():
                for path in directory.rglob('*'):
                    if path.is_file() and path.name not in {'reader.html', 'reader.epub'}:
                        if path.relative_to(root).as_posix() not in outputs:
                            raise SourceError('Unexpected existing work contents: ' + entry['work_id'])
    for path, data in pending:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.ingest-', delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(data)
            temporary.replace(path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
    return len(pending)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('package', type=Path)
    parser.add_argument('--stage', type=Path, help='Write drafts outside the published archive')
    parser.add_argument('--apply', action='store_true', help='Apply exactly the reviewed source outputs')
    args = parser.parse_args()
    if bool(args.stage) == args.apply:
        parser.error('Choose exactly one of --stage or --apply')
    if args.stage and args.stage.resolve().is_relative_to((ROOT / 'archives').resolve()):
        parser.error('Stage outside the published archive')
    try:
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        outputs = plan_files(manifest, args.package, ROOT)
        target = ROOT if args.apply else args.stage.resolve()
        changed = write_files(outputs, target, apply=args.apply, manifest=manifest)
        print(f'{len(outputs)} source files accounted for; {changed} files written')
    except (SourceError, OSError, KeyError, ValueError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
