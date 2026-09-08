#!/usr/bin/env python3
"""Apply an offline, reviewed whole-catalogue source manifest.

Each source document has an explicit disposition. New works are assembled only
from approved documents; existing literary text is never overwritten. Hashes
freeze both the reviewed source inputs and the exact intended outputs.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET
from sahityaras_ingest import SourceError, digest, inventory, package_path, tag, xml
from sahityaras_text import extract_document
from sahityaras_members import extract_member
from sahityaras_batch import add_collection, encoded
from devanagari_slug import romanize
from sanitize_extracted_html import sanitize

ROOT = Path(__file__).resolve().parent.parent


def checked_id(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-z0-9_-]+',value):
        raise SourceError('Invalid archive identifier')
    return value


def included_files(work: dict, books: dict, cache: Path) -> dict[str, bytes]:
    sections=[]; captures=[]
    for source in work['sources']:
        book=books[source['book']]
        document=next(d for d in book['documents'] if d['path']==source['path'])
        if document['decision'] != ('split' if source.get('member') else 'include'):
            raise SourceError('Work includes an unapproved document')
        path=package_path(cache,cache/book['id'],source['path'])
        if digest(path.read_bytes())!=document['sha256']:
            raise SourceError('Changed literary source')
        if source.get('member'):
            member = next(m for m in document['members'] if m['id'] == source['member'])
            if member['decision'] != 'include':
                raise SourceError('Unapproved source member')
            result = extract_member(path.read_bytes(), numbers=member['numbers'],
                expected_total=document['member_count'], fallback_title=work['title'])
        else:
            result=extract_document(path.read_bytes(),notes_approved=document.get('notes_approved',False),
                remove_ids=tuple(document.get('remove_ids',[])),remove_links=tuple(document.get('remove_links',[])),
                fallback_title=document['title'],replacements=tuple(document.get('replacements',[])))
        section=result.text.rstrip('\n')
        if work.get('preserve_section_titles'):
            section=result.title+'\n\n'+section
        sections.append(section)
        captures.append(result.capture)
    text='\n\n'.join(sections)+'\n'
    if not sections:raise SourceError('Empty work source set')
    ns='{http://www.w3.org/1999/xhtml}'
    ET.register_namespace('',ns[1:-1])
    capture=ET.Element(ns+'html',{'lang':'ne'})
    head=ET.SubElement(capture,ns+'head')
    ET.SubElement(head,ns+'meta',{'charset':'utf-8'})
    ET.SubElement(head,ns+'title').text=work['title']
    body=ET.SubElement(capture,ns+'body')
    for index,data in enumerate(captures,1):
        oldbody=next(n for n in xml(data).iter() if tag(n)=='body')
        # Scope IDs within each source section to keep notes unambiguous.
        prefix=f'section-{index}-'
        for node in oldbody.iter():
            if node.get('id'):node.set('id',prefix+node.get('id'))
            if node.get('href','').startswith('#'):node.set('href','#'+prefix+node.get('href')[1:])
        section=ET.SubElement(body,ns+'section',{'id':f'section-{index}'})
        section.text=oldbody.text
        for node in oldbody:section.append(node)
    desc='Transcribed from the identified Sahitya Ras source edition. Source wording and literary structure retained; not checked against printed pages.'
    if work.get('description_note'):desc+=' '+work['description_note']
    metadata={
        'id':work['id'],'title':work['title'],'title_roman':work.get('title_roman') or romanize(work['title']).title(),
        'subtitle':None,'author':work['author'],'language':work.get('language','ne'),'script':'Devanagari','genre':work['genre'],
        'first_published':{'bs':None,'ad':None},'edition':work.get('edition'),'publisher':work.get('publisher'),
        'description':desc,'rights':work['rights'],
        'source':{'name':'Sahitya Ras (sahityaras.com)','url':work['source_url'],'pdf':None,'html':'extracted/index.html'},
        'pages':None,'text':{'extraction_method':'html','ocr_status':'born-digital','proofread':False,'quality':None},
        'formats':{'pdf':None,'txt':'text.txt','html':'reader.html','epub':'reader.epub'},
        'added':work['prepared_date'],'updated':work['prepared_date']}
    for collection in work.get('collections',[]):metadata=add_collection(metadata,collection)
    return {'text.txt':text.encode(),'metadata.json':encoded(metadata),
        'extracted/index.html':sanitize(ET.tostring(capture,encoding='utf-8',xml_declaration=True).decode('utf-8')+'\n').encode('utf-8')}


def plan(manifest: dict, cache: Path, root: Path, *, verify_outputs: bool=True) -> dict[str,bytes]:
    if manifest.get('schema_version')!=2:raise SourceError('Unsupported catalogue manifest')
    books={b['id']:b for b in manifest['books']}
    if len(books)!=len(manifest['books']):raise SourceError('Duplicate source book')
    for book in books.values():
        checked_id(book['id'])
        actual=inventory(cache/book['id']/'src')
        if actual['package_sha256']!=book['package_sha256']:raise SourceError('Changed package: '+book['id'])
        expected={d['path']:d for d in book['documents']}
        if len(expected)!=len(book['documents']):raise SourceError('Duplicate document decision')
        if set(expected)!={'src/'+d['path'] for d in actual['documents']}:raise SourceError('Incomplete document accounting: '+book['id'])
        for d in actual['documents']:
            e=expected['src/'+d['path']]
            if (e['sha256'],e['spine_position'])!=(d['sha256'],d['spine_position']):raise SourceError('Changed document/order')
            if e['decision'] not in {'include','map-existing','exclude','defer','split'} or not e.get('reason'):
                raise SourceError('Missing source disposition/reason')
            if e['decision'] == 'split':
                members = e.get('members', [])
                ids = [checked_id(m['id']) for m in members]
                numbers = [n for m in members for n in m['numbers']]
                if (not members or len(set(ids)) != len(ids)
                        or numbers != list(range(1, e['member_count'] + 1))):
                    raise SourceError('Incomplete numbered-member accounting')
                for member in members:
                    if member.get('decision') not in {'include', 'map-existing'} or not member.get('reason'):
                        raise SourceError('Unreviewed numbered member')
    outputs={}; destinations=set(); assigned=set()
    for work in manifest['works']:
        aid=checked_id(work['author']['id']);wid=checked_id(work['id'])
        base=f'archives/authors/{aid}/{wid}'
        if base in destinations:raise SourceError('Repeated work destination')
        destinations.add(base)
        if work['rights']['status'] not in {'public-domain','permission-granted'}:raise SourceError('Rights gate')
        if not work.get('reviewed'):raise SourceError('Unreviewed work')
        for source in work.get('sources',[])+work.get('mapped_sources',[]):
            key=(source['book'],source['path'],source.get('member'))
            if source.get('member'):
                document = next(d for d in books[source['book']]['documents'] if d['path'] == source['path'])
                member = next(m for m in document.get('members', []) if m['id'] == source['member'])
                if member.get('destination') != base:
                    raise SourceError('Numbered member assigned to the wrong work')
            if key in assigned:raise SourceError('Source document assigned twice')
            assigned.add(key)
        if work['decision']=='include':
            files=included_files(work,books,cache)
        elif work['decision']=='map-existing':
            folder=root/base
            if digest((folder/'text.txt').read_bytes())!=work['baseline_text_sha256']:
                raise SourceError('Existing literary text changed: '+wid)
            current=(folder/'metadata.json').read_bytes()
            metadata=json.loads(current)
            if metadata['author']!=work['author']:raise SourceError('Author identity changed')
            for collection in work.get('collections',[]):metadata=add_collection(metadata,collection)
            updated=encoded(metadata)
            if digest(current)!=work['baseline_metadata_sha256'] and current!=updated:
                raise SourceError('Existing metadata changed: '+wid)
            files={'metadata.json':updated}
        else:raise SourceError('Unknown work decision')
        if verify_outputs and {k:digest(v) for k,v in files.items()}!=work['outputs']:
            raise SourceError('Extraction differs from reviewed output: '+wid)
        for name,data in files.items():outputs[base+'/'+name]=data
    expected_assignments = set()
    for b in books.values():
        for d in b['documents']:
            if d['decision'] in {'include', 'map-existing'}:
                expected_assignments.add((b['id'], d['path'], None))
            elif d['decision'] == 'split':
                expected_assignments.update((b['id'], d['path'], m['id']) for m in d['members'])
    if assigned!=expected_assignments:raise SourceError('Literary source assignment incomplete')
    return outputs


def write(outputs, manifest, root, *, apply=False):
    existing={f"archives/authors/{w['author']['id']}/{w['id']}/metadata.json":w
              for w in manifest['works'] if w['decision']=='map-existing'}
    pending=[]
    for rel,data in outputs.items():
        path=root/rel
        if not path.resolve().is_relative_to(root.resolve()):raise SourceError('Destination outside root')
        if path.is_symlink():raise SourceError('Symlink destination')
        if path.exists():
            old=path.read_bytes()
            if old==data:continue
            allowed=existing.get(rel) if apply else None
            if not allowed or digest(old)!=allowed['baseline_metadata_sha256']:
                raise SourceError('Refusing changed destination: '+rel)
        pending.append((path,data))
    if apply:
        for w in manifest['works']:
            if w['decision']!='include':continue
            folder=root/'archives/authors'/w['author']['id']/w['id']
            for path in folder.rglob('*'):
                if path.is_file() and path.name not in {'reader.html','reader.epub'} and path.relative_to(root).as_posix() not in outputs:
                    raise SourceError('Unexpected work contents: '+w['id'])
    for path,data in pending:
        path.parent.mkdir(parents=True,exist_ok=True)
        temp=None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.ingest-',delete=False) as h:
                temp=Path(h.name);h.write(data)
            temp.replace(path)
        finally:
            if temp is not None and temp.exists():temp.unlink()
    return len(pending)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest',type=Path);p.add_argument('cache',type=Path)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--stage',type=Path);mode.add_argument('--apply',action='store_true')
    args=p.parse_args()
    if args.stage and args.stage.resolve().is_relative_to((ROOT/'archives').resolve()):p.error('Stage outside archives')
    try:
        m=json.loads(args.manifest.read_text());out=plan(m,args.cache,ROOT)
        count=write(out,m,ROOT if args.apply else args.stage.resolve(),apply=args.apply)
        print(f'{len(m["books"])} books accounted for; {len(out)} source files; {count} written')
    except (SourceError,OSError,KeyError,ValueError) as e:p.exit(1,str(e)+'\n')

if __name__=='__main__':main()
