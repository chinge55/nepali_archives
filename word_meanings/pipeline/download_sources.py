#!/usr/bin/env python3
"""Fetch recorded dictionary snapshots for local evaluation; require exact hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    manifest = json.loads((ROOT / 'sources.json').read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=[s['id'] for s in manifest], help='Fetch only this source')
    args = parser.parse_args()
    raw = ROOT / 'data/raw'
    raw.mkdir(parents=True, exist_ok=True)
    for source in manifest:
        if args.source and source['id'] != args.source:
            continue
        name = source['file']
        if Path(name).name != name or not source['url'].startswith('https://'):
            raise SystemExit('Manifest requires a plain filename and an HTTPS source URL.')
        destination = raw / name
        if destination.exists():
            if sha256(destination) != source['sha256']:
                raise SystemExit(f'{name}: existing file differs from the recorded snapshot; inspect it before proceeding.')
            print(f'{name}: existing snapshot verified')
            continue
        temporary = None
        try:
            request = urllib.request.Request(source['url'], headers={'User-Agent': 'NepaliArchives-dictionary-research/1.0'})
            with urllib.request.urlopen(request, timeout=60) as response, tempfile.NamedTemporaryFile(dir=raw, suffix='.part', delete=False) as stream:
                temporary = Path(stream.name)
                while chunk := response.read(1024 * 1024):
                    stream.write(chunk)
            if sha256(temporary) != source['sha256']:
                raise SystemExit(f'{name}: upstream does not match the recorded snapshot. Obtain that snapshot or explicitly review a manifest update; the downloaded data was not installed.')
            temporary.replace(destination)
            print(f'{name}: downloaded and verified')
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
