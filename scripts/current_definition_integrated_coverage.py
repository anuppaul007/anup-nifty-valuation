#!/usr/bin/env python3
"""All-50 coverage audit for a clean 31-Aug-2026 integrated-filing anchor.

The anchor is chosen so the four latest completed result quarters available by
31-Aug-2026 (Sep-2025, Dec-2025, Mar-2026, Jun-2026) are all inside NSE's
Integrated Filing - Financials regime. Research only; no live model changes.

For each quarter, consolidated results are required when available; standalone
is accepted only when no consolidated filing exists for that quarter, matching
the current NIFTY valuation-methodology fallback rule.
"""
from __future__ import annotations
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import json,re,time,zipfile
import pdfplumber,requests

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'current_definition_integrated_coverage.json'
UA={'accept':'*/*','accept-language':'en-US,en;q=0.9','user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36','sec-fetch-dest':'empty','sec-fetch-mode':'cors','sec-fetch-site':'same-origin'}
TARGET={'30-SEP-2025','31-DEC-2025','31-MAR-2026','30-JUN-2026'}

def session():
    s=requests.Session();s.headers.update(UA)
    for u in ('https://www.nseindia.com/','https://www.nseindia.com/companies-listing/corporate-integrated-filing','https://www.niftyindices.com/'):
        try:s.get(u,timeout=20);time.sleep(.4)
        except Exception:pass
    return s

def weight_rows(s):
    url='https://www.niftyindices.com/Indices_-_Market_Capitalisation_and_Weightage/indices_dataAug2026.zip'
    r=s.get(url,timeout=40,headers={**UA,'referer':'https://www.niftyindices.com/reports/monthly-reports'});r.raise_for_status()
    z=zipfile.ZipFile(BytesIO(r.content));name=next(n for n in z.namelist() if re.search(r'NIFTY_50_Aug2026\.pdf$',n,re.I));pdf=z.read(name)
    rows=[]
    with pdfplumber.open(BytesIO(pdf)) as doc:
        for p in doc.pages:
            tbl=p.extract_table() or []
            for rr in tbl[1:]:
                if not rr or len(rr)<6:continue
                sym=str(rr[0] or '').strip();sec=re.sub(r'\s+',' ',str(rr[1] or '')).strip()
                try:price=float(str(rr[3] or '').replace(',',''));mcap=float(str(rr[4] or '').replace(',',''));wt=float(str(rr[5] or '').replace(',',''))
                except Exception:continue
                if sym:rows.append({'symbol':sym,'security_name':sec,'price':price,'index_mcap_cr':mcap,'published_weight_pct':wt})
    q={r['symbol']:r for r in rows};rows=list(q.values());return rows,{'url':url,'pdf':name,'count':len(rows),'weight_sum':sum(r['published_weight_pct'] for r in rows)}

def issuer_variants(name):
    vals=[name]
    vals.append(re.sub(r'\bLtd\.?$', 'Limited', name, flags=re.I))
    vals.append(name.replace(' Ltd.',' Limited').replace(' Ltd',' Limited'))
    return list(dict.fromkeys(v.strip() for v in vals if v.strip()))

def listing(s,symbol,issuer):
    url='https://www.nseindia.com/api/integrated-filing-results'
    params={'index':'equities','symbol':symbol,'issuer':issuer,'period_ended':'all','type':'Integrated Filing- Financials','page':1,'size':50}
    for attempt in range(4):
        try:
            r=s.get(url,params=params,headers={**UA,'referer':'https://www.nseindia.com/companies-listing/corporate-integrated-filing'},timeout=30)
            if r.status_code in (401,403,500):
                try:s.get('https://www.nseindia.com/',timeout=15)
                except Exception:pass
                time.sleep(1.0*(attempt+1));continue
            r.raise_for_status();d=r.json();return d.get('data',[]) if isinstance(d,dict) else []
        except Exception:
            time.sleep(1.0*(attempt+1))
    return []

def choose_basis(rows,quarter):
    qrows=[x for x in rows if str(x.get('qe_Date') or '').upper().strip()==quarter]
    cons=[x for x in qrows if str(x.get('consolidated') or '').strip().lower()=='consolidated']
    stand=[x for x in qrows if str(x.get('consolidated') or '').strip().lower()=='standalone']
    chosen=cons or stand
    if not chosen:return None,None
    # Original/revision duplicates: latest creation/revision record is the point-in-time record available now;
    # the full ratio reconstruction will separately enforce availability by anchor date.
    row=chosen[0]
    return row,('consolidated' if cons else 'standalone_fallback')

def audit_symbol(s,row):
    best=[];used=None
    for issuer in issuer_variants(row['security_name'])+['']:
        rows=listing(s,row['symbol'],issuer)
        if len(rows)>len(best):best=rows;used=issuer
        if rows:break
    found={};basis={}
    for q in TARGET:
        chosen,b=choose_basis(best,q)
        if chosen is not None:
            found[q]=chosen;basis[q]=b
    got=set(found)
    return {**row,'issuer_used':used,'listing_count':len(best),'target_quarters_found':sorted(got),'target_quarters_missing':sorted(TARGET-got),'basis_by_quarter':basis,'complete_four_quarters':got==TARGET}

def main():
    s=session();rows,meta=weight_rows(s);out=[]
    for r in rows:
        out.append(audit_symbol(s,r));time.sleep(.35)
    complete=sum(x['complete_four_quarters'] for x in out)
    result={'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'research_only':True,'anchor_date':'2026-08-31','target_quarters':sorted(TARGET),'basis_rule':'consolidated when available; standalone only when consolidated unavailable','weight_source':meta,'coverage':{'complete':complete,'required':50,'failed':len(out)-complete},'failures':[{'symbol':x['symbol'],'security_name':x['security_name'],'listing_count':x['listing_count'],'missing':x['target_quarters_missing'],'issuer_used':x['issuer_used']} for x in out if not x['complete_four_quarters']],'standalone_fallbacks':[{'symbol':x['symbol'],'quarters':[q for q,b in x['basis_by_quarter'].items() if b=='standalone_fallback']} for x in out if any(b=='standalone_fallback' for b in x['basis_by_quarter'].values())],'constituents':out,'live_model_changed':False,'live_allocation_changed':False}
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'weight_count':meta['count'],'coverage':result['coverage'],'standalone_fallbacks':result['standalone_fallbacks'],'failures':result['failures'][:15]},indent=2))

if __name__=='__main__':main()
