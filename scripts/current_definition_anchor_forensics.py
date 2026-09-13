#!/usr/bin/env python3
"""Forensics for the strict 31-Aug-2026 current-definition anchor.

Research only. This script answers two narrow questions before any formula is
changed:

1) What date does the official Aug-2026 NIFTY 50 monthly weight PDF actually
   state for its snapshot?
2) What do the underlying XBRL period contexts and profit-like facts say for
   the suspicious Mar-2026 ADANIPORTS and INDIGO filings?

No ratio tolerance, accounting rule, live model or allocation is changed.
"""
from __future__ import annotations
from datetime import datetime,timezone
from io import BytesIO
from pathlib import Path
import json,re,time,zipfile,xml.etree.ElementTree as ET
import pdfplumber
import current_definition_integrated_anchor as a
import current_definition_integrated_coverage as cov

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'current_definition_anchor_forensics.json'
TARGET_SYMBOLS=['ADANIPORTS','INDIGO']
TARGET_QUARTER='31-MAR-2026'


def local(tag):return tag.split('}')[-1].split(':')[-1]


def weight_pdf_forensics(s):
    url='https://www.niftyindices.com/Indices_-_Market_Capitalisation_and_Weightage/indices_dataAug2026.zip'
    r=s.get(url,headers={**cov.UA,'referer':'https://www.niftyindices.com/reports/monthly-reports'},timeout=45);r.raise_for_status()
    z=zipfile.ZipFile(BytesIO(r.content))
    name=next(n for n in z.namelist() if re.search(r'NIFTY_50_Aug2026\.pdf$',n,re.I))
    pdf=z.read(name)
    with pdfplumber.open(BytesIO(pdf)) as doc:
        first=(doc.pages[0].extract_text() or '').strip()
        all_text='\n'.join((p.extract_text() or '') for p in doc.pages)
    # Keep explicit date-like strings exactly as printed; do not infer a date
    # from the filename if the document itself does not state one.
    pats=[
      r'(?i)(?:as\s+on|as\s+of|data\s+as\s+on|for\s+the\s+month\s+ended)\s*[:\-]?\s*([^\n]{0,60})',
      r'\b(?:31|30|29|28)[\-/ ](?:Aug(?:ust)?|08)[\-/ , ]+2026\b',
      r'\bAug(?:ust)?\s+(?:31|30|29|28),?\s+2026\b',
    ]
    matches=[]
    for p in pats:
        matches.extend(re.findall(p,all_text))
    # re.findall may return full strings or captured substrings.
    matches=[re.sub(r'\s+',' ',str(x)).strip() for x in matches if str(x).strip()]
    return {
      'url':url,'pdf':name,'pages':len(pdf) if False else None,
      'first_page_text':re.sub(r'[ \t]+',' ',first),
      'date_like_matches':list(dict.fromkeys(matches)),
      'contains_31_aug_2026':bool(re.search(r'(?i)(?:31[\-/ ](?:Aug(?:ust)?|08)[\-/ , ]+2026|Aug(?:ust)?\s+31,?\s+2026)',all_text)),
    }


def context_map(root):
    out={}
    for c in root.iter():
        if local(c.tag)!='context':continue
        cid=str(c.attrib.get('id') or '')
        item={'id':cid,'start':None,'end':None,'instant':None,'dimensions':[]}
        for e in c.iter():
            n=local(e.tag)
            if n=='startDate':item['start']=(e.text or '').strip()
            elif n=='endDate':item['end']=(e.text or '').strip()
            elif n=='instant':item['instant']=(e.text or '').strip()
            elif n in ('explicitMember','typedMember'):
                item['dimensions'].append({'tag':n,'dimension':e.attrib.get('dimension'),'value':(e.text or '').strip()})
        out[cid]=item
    return out


def profit_like(name):
    n=name.lower()
    return any(k in n for k in ('profit','loss','earnings')) and not any(k in n for k in ('per_share','pershare','beforeinterest'))


def filing_forensics(s,row):
    listings,issuer=a.listings_for(s,row)
    selected,basis=a.choose_quarter(listings,TARGET_QUARTER)
    if not selected:raise ValueError('missing_mar_2026_filing')
    root=a.fetch_xml(s,selected['xbrl']);ctx=context_map(root)
    facts=[]
    for e in root.iter():
        cr=e.attrib.get('contextRef');txt=(e.text or '').strip();name=local(e.tag)
        if not cr or not txt or not profit_like(name):continue
        try:v=float(txt.replace(',',''))
        except Exception:continue
        facts.append({'name':name,'context':str(cr),'value':v,'unitRef':e.attrib.get('unitRef'),'decimals':e.attrib.get('decimals'),'period':ctx.get(str(cr))})
    facts=sorted(facts,key=lambda x:(x['context'],x['name'],x['value']))
    selected_profit=a.profit_from(a.numeric_facts(root))
    return {
      'symbol':row['symbol'],'issuer_used':issuer,'basis':basis,
      'filing_time':str(a.filing_time(selected)),'xbrl':selected['xbrl'],
      'selected_profit_fact':selected_profit,
      'contexts_of_interest':{k:v for k,v in ctx.items() if k.lower() in {'oned','twod','threed','fourd','onei','twoi','threei','fouri'}},
      'profit_like_facts':facts,
    }


def main():
    s=cov.session();rows,wmeta=cov.weight_rows(s);by={r['symbol']:r for r in rows}
    out={
      'schema_version':1,'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
      'research_only':True,'anchor_date':'2026-08-31','weight_source_metadata':wmeta,
      'weight_pdf':weight_pdf_forensics(s),'march_xbrl':{},
      'live_model_changed':False,'live_allocation_changed':False,'tolerances_changed':False,
    }
    for sym in TARGET_SYMBOLS:
        try:out['march_xbrl'][sym]=filing_forensics(s,by[sym])
        except Exception as e:out['march_xbrl'][sym]={'error':f'{type(e).__name__}: {e}'}
        time.sleep(.5)
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print(json.dumps({'weight_pdf':out['weight_pdf'],'march':{k:{'basis':v.get('basis'),'filing_time':v.get('filing_time'),'selected_profit_fact':v.get('selected_profit_fact'),'contexts':v.get('contexts_of_interest')} for k,v in out['march_xbrl'].items()}},indent=2,default=str))

if __name__=='__main__':main()
