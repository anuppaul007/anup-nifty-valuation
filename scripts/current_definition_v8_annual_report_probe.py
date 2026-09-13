#!/usr/bin/env python3
"""V8 P/B source probe: locate consolidated equity/net-worth lines in PIT annual reports.

This is deliberately a discovery diagnostic, not a production number extractor.
For representative NIFTY heavyweights it:
  * fetches the latest official NSE annual report available by 31-Aug-2026;
  * downloads that official report;
  * extracts text pages with consolidated balance-sheet / equity / net-worth
    vocabulary using pdfplumber;
  * records short page-local snippets and candidate numeric lines.

No candidate is chosen by closeness to published NIFTY P/B. OCR is not used.
"""
from __future__ import annotations
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import json, re, time
import pandas as pd
import pdfplumber, requests

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'current_definition_v8_annual_report_probe.json'
ANCHOR=pd.Timestamp('2026-08-31 23:59:59')
SYMBOLS=['RELIANCE','HDFCBANK','ICICIBANK','INFY','TCS','SBIN','BHARTIARTL','LT']
API='https://www.nseindia.com/api/annual-reports'
UA={
 'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36',
 'Accept':'application/json,text/plain,*/*','Accept-Language':'en-US,en;q=0.9',
}


def session():
    s=requests.Session();s.headers.update(UA)
    for u in ('https://www.nseindia.com/','https://www.nseindia.com/companies-listing/corporate-filings-annual-reports'):
        try:s.get(u,timeout=20);time.sleep(.3)
        except Exception:pass
    return s


def dt(x):
    if not x:return None
    d=pd.to_datetime(str(x),dayfirst=True,errors='coerce')
    return None if pd.isna(d) else d


def report_rows(s,symbol):
    p={'index':'equities','symbol':symbol};last=None
    for attempt in range(5):
        try:
            r=s.get(API,params=p,headers={**UA,'Referer':f'https://www.nseindia.com/companies-listing/corporate-filings-annual-reports?symbol={symbol}&tabIndex=equity'},timeout=30)
            if r.status_code in (401,403,500):
                try:s.get('https://www.nseindia.com/',timeout=15)
                except Exception:pass
                time.sleep(1+attempt);continue
            r.raise_for_status();d=r.json()
            if isinstance(d,list):return d
            if isinstance(d,dict):
                if isinstance(d.get('data'),list):return d['data']
                rows=[]
                for v in d.values():
                    if isinstance(v,list):rows.extend(x for x in v if isinstance(x,dict))
                return rows
            return []
        except Exception as e:last=e;time.sleep(1+attempt)
    raise last or RuntimeError('annual_report_api_failed')


def broadcast(r):
    for k in ('broadcast_dttm','broadcastDate','broadcastDateTime','disseminationDateTime','date'):
        d=dt(r.get(k))
        if d is not None:return d
    return None


def url_of(r):
    for k in ('fileName','file_name','attachment','attchmntFile','url'):
        v=r.get(k)
        if isinstance(v,str) and v.startswith('http'):return v
    return None


def year_key(r):
    vals=[]
    for k in ('fromYear','from_year','fromYr','fromyear','toYear','to_year','toYr','toyear'):
        try:vals.append(int(r.get(k)))
        except Exception:pass
    return max(vals) if vals else -1


def latest_pit(rows):
    q=[]
    for r in rows:
        b=broadcast(r);u=url_of(r)
        if b is not None and b<=ANCHOR and u:q.append((year_key(r),b,r,u))
    if not q:return None
    q.sort(key=lambda x:(x[0],x[1]),reverse=True)
    _,b,r,u=q[0];return {'broadcast':str(b),'url':u,'raw':r}


def download_pdf(s,url):
    # Annual-report API sometimes points directly to PDF and sometimes a zip.
    r=s.get(url,headers={**UA,'Referer':'https://www.nseindia.com/'},timeout=80);r.raise_for_status()
    data=r.content
    if data[:4]==b'%PDF':return data,'pdf'
    if data[:2]==b'PK':
        import zipfile
        z=zipfile.ZipFile(BytesIO(data));names=[n for n in z.namelist() if n.lower().endswith('.pdf')]
        if not names:raise ValueError('annual_report_zip_without_pdf')
        # Official annual-report package should contain the report PDF; choose the
        # largest PDF, not a ratio-fitting file.
        name=max(names,key=lambda n:z.getinfo(n).file_size)
        return z.read(name),'zip:'+name
    raise ValueError('annual_report_not_pdf_or_zip')

KEYWORDS=('consolidated balance sheet','consolidated statement of financial position','total equity','net worth','networth','equity attributable to owners','other equity')
NUMERIC_LINE=re.compile(r'.*(?:total equity|net\s*worth|networth|other equity|equity attributable).*\d.*',re.I)


def probe_pdf(pdf):
    hits=[]
    with pdfplumber.open(BytesIO(pdf)) as doc:
        pages=len(doc.pages)
        for i,p in enumerate(doc.pages):
            text=p.extract_text() or ''
            low=text.lower()
            if not any(k in low for k in KEYWORDS):continue
            lines=[re.sub(r'\s+',' ',x).strip() for x in text.splitlines() if x.strip()]
            cand=[x for x in lines if NUMERIC_LINE.match(x)]
            balance=any(k in low for k in ('consolidated balance sheet','consolidated statement of financial position'))
            # Preserve a compact context window around the first balance-sheet/equity match.
            anchor=next((j for j,x in enumerate(lines) if any(k in x.lower() for k in KEYWORDS)),0)
            snippet=lines[max(0,anchor-3):min(len(lines),anchor+9)]
            hits.append({'page':i+1,'has_consolidated_balance_sheet_heading':balance,'candidate_lines':cand[:12],'context_snippet':snippet})
            if len(hits)>=18:break
    return {'pages':pages,'hits':hits}


def main():
    s=session();out={};errors=[]
    for sym in SYMBOLS:
        try:
            rows=report_rows(s,sym);chosen=latest_pit(rows)
            if not chosen:raise ValueError('no_pit_annual_report')
            pdf,fmt=download_pdf(s,chosen['url']);probe=probe_pdf(pdf)
            out[sym]={'report_api_rows':len(rows),'chosen':chosen,'download_format':fmt,'pdf_bytes':len(pdf),**probe}
        except Exception as e:errors.append({'symbol':sym,'error':f'{type(e).__name__}: {e}'})
        time.sleep(.4)
    result={'schema_version':1,'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'research_only':True,'anchor_date':'2026-08-31','symbols':SYMBOLS,'coverage':{'ok':len(out),'required':len(SYMBOLS),'failed':len(errors)},'failed':errors,'cases':out,'selection_guardrail':'Latest PIT annual report by official year/broadcast metadata; PDF lines are surfaced semantically and are not selected by closeness to published NIFTY P/B.','ocr_used':False,'live_model_changed':False,'live_allocation_changed':False,'tolerances_changed':False}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print(json.dumps({'coverage':result['coverage'],'headline':{s:{'broadcast':v['chosen']['broadcast'],'pages':v['pages'],'hit_pages':[h['page'] for h in v['hits'][:8]],'candidate_lines':[x for h in v['hits'] for x in h['candidate_lines'][:2]][:8]} for s,v in out.items()},'failed':errors},indent=2,ensure_ascii=False))

if __name__=='__main__':main()
