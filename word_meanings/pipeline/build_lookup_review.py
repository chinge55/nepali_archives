#!/usr/bin/env python3
"""Keep reviewed lookup associations separate from spelling corrections and suggestions."""
from pathlib import Path
from collections import defaultdict,Counter
import csv,json,sqlite3,unicodedata
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent
REVIEW=ROOT/'review'
OUT=ROOT/'data/review'
OUT.mkdir(parents=True,exist_ok=True)

def norm(s):return ' '.join(unicodedata.normalize('NFC',s).split())
def relaxed(s):return norm(s).replace('\u200c','').replace('\u200d','')

c=sqlite3.connect(ROOT/'data/combined/dictionary.sqlite3')
headwords=set();nominals=set();relaxed_index=defaultdict(set)
for w,definition in c.execute('SELECT lookup_key,definitions_json FROM entries WHERE has_definition=1'):
 headwords.add(w);relaxed_index[relaxed(w)].add(w)
 for group in json.loads(definition):
  grammar=group.get('grammar') or ''
  if 'ना.' in grammar or grammar in ('noun','name','proper-noun','proper-name'):
   nominals.add(w)
# These generate visible analysis candidates only. A dictionary hit does not validate a derivation.
suffixes=['हरूसँग','हरूबाट','हरूलाई','हरूको','हरूका','हरूकी','हरूमा','हरूले','हरूमै','हरूकै',
          'हरुसँग','हरुबाट','हरुलाई','हरुको','हरुका','हरुकी','हरुमा','हरुले',
          'सँगको','सँगका','सँगकी','बाटको','बाटका','बाटकी','सम्मको','सम्मका','सम्मकी',
          'हरू','हरु','सँग','बाट','सम्म','तिर','लाई','ले','को','का','की','मा','कै','मै']
records=[]
reviewfile=REVIEW/'lookup-review.json'
if reviewfile.exists():
 loaded=json.loads(reviewfile.read_text())
 records=loaded["records"] if isinstance(loaded,dict) else loaded
 assert isinstance(records,list)
reviewed={};accepted={}
for r in records:
 form=norm(r['form']);assert form not in reviewed,form
 reviewed[form]=r
 if r.get('status')!='accepted':continue
 assert r.get('classification') and r.get('explanation') and r.get('evidence'),form
 targets=[norm(w) for w in r.get('headwords',[])]
 if not targets:continue
 assert all(w in headwords for w in targets),(form,targets)
 for e in r['evidence']:
  p=REPO/e['path'];line=e.get('line');text=e.get('text','')
  assert p.is_file() and text, (form,'missing source evidence')
  source=p.read_text()
  assert text in source,(form,'source evidence not found')
  import re
  chars=''.join(chr(i) for lo,hi in [(0x900,0x97f),(0xa8e0,0xa8ff)] for i in range(lo,hi+1) if unicodedata.category(chr(i))[0] in 'LM')+'\u200c\u200d'
  assert re.search('(?<!['+chars+'])'+re.escape(form)+'[\u200c\u200d]*(?!['+chars+'])',norm(text)),(form,'evidence contains no complete token')
  if isinstance(line,int):
   source_line=source.splitlines()[line-1]
   assert text in source_line,(form,'line mismatch')
   assert re.search('(?<!['+chars+'])'+re.escape(form)+'[\u200c\u200d]*(?!['+chars+'])',norm(source_line)),(form,'source line contains no complete token')
 accepted[form]=r
rows=list(csv.DictReader((ROOT/'data/combined/vocabulary.csv').open()))
summary=Counter();candidates_count=Counter();lookup={};queue=[]
for row in rows:
 w=row['word'];n=int(row['occurrences']);status='unresolved';targets=[];candidates=[]
 if w in headwords:
  status='exact';targets=[w]
 elif w in accepted:
  status='reviewed_association';targets=accepted[w]['headwords']
 elif relaxed(w) in relaxed_index:
  status='unicode_joiner_equivalent';targets=sorted(relaxed_index[relaxed(w)])
 else:
  for suffix in suffixes:
   if w.endswith(suffix):
    stem=w[:-len(suffix)]
    if len(stem)>=2 and stem in nominals:
     candidates.append({'headword':stem,'suffix':suffix,'kind':'nominal_suffix_candidate'})
  if candidates:status='unreviewed_morphology_candidate'
 summary[status+'_forms']+=1;summary[status+'_tokens']+=n
 if status!='exact':
  evidence=reviewed.get(w)
  queue.append({**row,'lookup_status':status,'headwords':targets,'candidates':candidates,
                'review':evidence})
  if targets:
   lookup[w]={'headwords':targets,'kind':status,'classification':evidence.get('classification') if evidence else 'unicode',
              'explanation':evidence.get('explanation') if evidence else 'Equivalent spelling with zero-width joining controls.',
              'requires_context':len(targets)>1,'sense_selection':'not_inferred','changes_original_text':False}
with (OUT/'word-review-queue.jsonl').open('w') as f:
 for r in queue:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
(OUT/'lookup-associations.json').write_text(json.dumps(lookup,ensure_ascii=False,indent=2)+'\n')
# No morphology candidate is silently promoted into the reviewed association layer.
assert all(v['kind']!='unreviewed_morphology_candidate' for v in lookup.values())
report={'review_records':len(records),'accepted_associations':len(accepted),'counts':dict(summary),
        'available_lookup_tokens':sum(summary[s+'_tokens'] for s in ['exact','reviewed_association','unicode_joiner_equivalent']),
        'total_tokens':sum(int(r['occurrences']) for r in rows),
        'review_status_counts':dict(Counter(r.get('status','unspecified') for r in records)),
        'coverage_note':'Lookup availability only; a dictionary hit does not establish spelling correctness or a passage-specific meaning.',
        'candidate_note':'Suffix matches are suggestions for review, not corrected words or verified coverage.',
        'preservation_note':'Associations affect dictionary lookup only; no source text is rewritten.'}
report['available_lookup_token_pct']=round(100*report['available_lookup_tokens']/report['total_tokens'],2)
(OUT/'lookup-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
