#!/usr/bin/env python3
"""
devanagari_slug.py — best-effort natural-Nepali romanization for slugs.

Harvard-Kyoto (what we first used) keeps every inherent schwa (पागल -> "pagala")
and uses v/z where Nepali reads b/sh. This produces friendlier slugs:
  * inherent schwa rendered, then the WORD-FINAL schwa is dropped UNLESS the
    final consonant follows a conjunct cluster (पागल->pagal, but वसन्त->basanta);
  * व -> b, श/ष -> sh, स -> s (Nepali phonology);
  * spaces -> "_".
Schwa deletion in Devanagari is linguistically irregular, so treat output as a
starting point to review, not ground truth.
"""
import re

VOW = {'अ':'a','आ':'a','इ':'i','ई':'i','उ':'u','ऊ':'u','ऋ':'ri','ॠ':'ri',
       'ए':'e','ऐ':'ai','ओ':'o','औ':'au','ऎ':'e','ऒ':'o','ॲ':'a','ऍ':'e','ऑ':'o'}
MAT = {'ा':'a','ि':'i','ी':'i','ु':'u','ू':'u','ृ':'ri','ॄ':'ri',
       'े':'e','ै':'ai','ो':'o','ौ':'au','ॅ':'e','ॉ':'o','ॆ':'e','ॊ':'o'}
CON = {'क':'k','ख':'kh','ग':'g','घ':'gh','ङ':'ng','च':'ch','छ':'chh','ज':'j',
       'झ':'jh','ञ':'ny','ट':'t','ठ':'th','ड':'d','ढ':'dh','ण':'n','त':'t',
       'थ':'th','द':'d','ध':'dh','न':'n','प':'p','फ':'ph','ब':'b','भ':'bh',
       'म':'m','य':'y','र':'r','ल':'l','व':'b','श':'sh','ष':'sh','स':'s','ह':'h',
       'ळ':'l','क्ष':'ksh','त्र':'tr','ज्ञ':'gya','श्र':'shr',
       'ड़':'r','ढ़':'rh','फ़':'f','ज़':'z','य़':'y','क़':'k','ख़':'kh','ग़':'g'}
SIGN = {'ं':'n','ँ':'','ः':'h','ऽ':'','ॐ':'om'}
VIRAMA = '्'
ZWNJ, ZWJ = '‌', '‍'

# multi-codepoint conjuncts to handle before the char loop
DIGRAPH = [('क्ष','ksh'),('त्र','tr'),('ज्ञ','gya'),('श्र','shr'),
           ('ड़','r'),('ढ़','rh'),('फ़','f'),('ज़','z')]

class Tok:
    __slots__=('r','schwa','conj')
    def __init__(self,r,schwa=False,conj=False):
        self.r=r; self.schwa=schwa; self.conj=conj  # schwa: trailing inherent 'a'; conj: preceded by virama

def _romanize_word(w):
    for d,r in DIGRAPH:
        w=w.replace(d, '\x00'+r+'\x01')   # protect; \x00 marks a consonant w/ inherent schwa
    toks=[]
    i=0; prev_virama=False
    while i<len(w):
        ch=w[i]
        if ch=='\x00':                      # start of a protected digraph consonant
            j=w.index('\x01',i)
            toks.append(Tok(w[i+1:j], schwa=True, conj=prev_virama))
            prev_virama=False; i=j+1; continue
        if ch in (ZWNJ,ZWJ): i+=1; continue
        if ch in CON:
            toks.append(Tok(CON[ch], schwa=True, conj=prev_virama)); prev_virama=False; i+=1; continue
        if ch in MAT:
            if toks: toks[-1].r+=MAT[ch]; toks[-1].schwa=False
            else: toks.append(Tok(MAT[ch]))
            i+=1; continue
        if ch==VIRAMA:
            if toks: toks[-1].schwa=False
            prev_virama=True; i+=1; continue
        if ch in VOW: toks.append(Tok(VOW[ch])); prev_virama=False; i+=1; continue
        if ch in SIGN:
            if SIGN[ch]:
                if toks:
                    if toks[-1].schwa:          # resolve inherent vowel before the nasal
                        toks[-1].r+='a'; toks[-1].schwa=False
                    toks[-1].r+=SIGN[ch]
                else: toks.append(Tok(SIGN[ch]))
            i+=1; continue
        # unknown (digit, punctuation) -> keep if alnum-ish, else drop
        if ch.isalnum(): toks.append(Tok(ch))
        i+=1
    # word-final schwa deletion: drop trailing inherent 'a' unless that consonant
    # follows a conjunct cluster (keeps वसन्त -> basanta, but पागल -> pagal)
    for k in range(len(toks)-1,-1,-1):
        t=toks[k]
        if t.r=='' : continue
        if t.schwa and not t.conj:
            pass  # drop: emit without the inherent 'a' (r already has no 'a' appended)
        else:
            t.r += 'a' if t.schwa else ''
        break
    # all non-final schwa-bearing tokens keep their inherent 'a'
    out=[]
    for k,t in enumerate(toks):
        r=t.r
        if t.schwa and k!=_last_real(toks): r=r+'a'
        out.append(r)
    return ''.join(out)

def _last_real(toks):
    for k in range(len(toks)-1,-1,-1):
        if toks[k].r!='': return k
    return -1

def slugify(title):
    words=[w for w in re.split(r'\s+', title.strip()) if w]
    parts=[_romanize_word(w) for w in words]
    s='_'.join(parts).lower()
    s=re.sub(r'[^a-z0-9]+','_',s).strip('_')
    return s or 'work'

def romanize(title):
    """Clean, typeable display romanization (spaces, lowercase, pure ASCII) — same
    scheme as the slug: schwa dropped, व->b, श/ष->sh. No diacritics."""
    words=[w for w in re.split(r'\s+', title.strip()) if w]
    s=' '.join(_romanize_word(w) for w in words).lower()
    s=re.sub(r'[^a-z0-9 ]+',' ',s)
    return re.sub(r'\s+',' ',s).strip()

if __name__=='__main__':
    import sys
    for t in sys.argv[1:]:
        print(f"{t}  ->  {slugify(t)}")
