#!/usr/bin/env python3
"""V8 P/E gate: infer operational IWF using official shareholding XBRL total shares.

This is a falsification test, not an IWF estimator. For every 31-Aug-2026 NIFTY
50 constituent:
  effective IWF = official free-float index market cap / (price * total shares)
where total shares come independently from the 30-Jun-2026 official NSE
Shareholding Pattern XBRL.

The official public-shareholding percentage is a HARD UPPER BOUND on free-float
IWF. If inferred IWF exceeds public shareholding even after displayed-price and
market-cap rounding, either the June statutory share basis was not yet the
operational index basis or another timing/corporate-action detail is unresolved.
Public shareholding is never substituted as IWF.
"""
from __future__ import annotations
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import json, math, re, time, zipfile, xml.etree.ElementTree as ET
import pandas as pd
import pdfplumber, requests

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'current_definition_v8_iwf_bound.json'
WEIGHT_URL='https://www.niftyindices.com/Indices_-_Market_Capitalisation_and_Weightage/indices_dataAug2026.zip'
SH_API='https://www.nseindia.com/api/corporate-share-holdings-master'
UA={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36','Accept':'*/*','Accept-Language':'en-US,en;q=0.9'}


def session():
    s=requests.Session();s.headers.update(UA)
    for u in ('https://www.nseindia.com/','https://www.niftyindices.com/'):
        try:s.get(u,timeout=20);time.sleep(.3)
        except Exception:pass
    return s


def weight_rows(s):
    r=s.get(WEIGHT_URL,headers={**UA,'Referer':'https://www.niftyindices.com/reports/monthly-reports'},timeout=40);r.raise_for_status()
    z=zipfile.ZipFile(BytesIO(r.content));name=next(n for n in z.namelist() if re.search(r'NIFTY_50_Aug2026\.pdf$',n,re.I));pdf=z.read(name)
    rows=[];header_text=''
    with pdfplumber.open(BytesIO(pdf)) as doc:
        for p in doc.pages:
            header_text += '\n'+(p.extract_text() or '')[:1200]
            tbl=p.extract_table() or []
            for rr in tbl[1:]:
                if not rr or len(rr)<6:continue
                try:
                    sym=str(rr[0] or '').strip();price=float(str(rr[3]).replace(',',''));mcap=float(str(rr[4]).replace(',',''));wt=float(str(rr[5]).replace(',',''))
                except Exception:continue
                if sym:rows.append({'symbol':sym,'price':price,'index_mcap_cr':mcap,'published_weight_pct':wt})
    rows=list({r['symbol']:r for r in rows}.values())
    if len(rows)!=50:raise RuntimeError(f'weight_count_{len(rows)}')
    if 'August 31, 2026' not in header_text and 'August 31 2026' not in header_text:raise RuntimeError('weight_pdf_anchor_date_not_verified')
    return rows,{'url':WEIGHT_URL,'pdf':name,'count':len(rows),'weight_sum':sum(x['published_weight_pct'] for x in rows)}


def dt(x):
    d=pd.to_datetime(str(x),dayfirst=True,errors='coerce')
    return None if pd.isna(d) else d


def share_rows(s,sym):
    p={'index':'equities','symbol':sym};last=None
    for attempt in range(5):
        try:
            r=s.get(SH_API,params=p,headers={**UA,'Referer':f'https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern?symbol={sym}&tabIndex=equity'},timeout=30)
            if r.status_code in (401,403,500):
                try:s.get('https://www.nseindia.com/',timeout=15)
                except Exception:pass
                time.sleep(1+attempt);continue
            r.raise_for_status();d=r.json();return d if isinstance(d,list) else d.get('data',[]) if isinstance(d,dict) else []
        except Exception as e:last=e;time.sleep(1+attempt)
    raise last or RuntimeError('shareholding_api_failed')


def june(rows):
    for r in rows:
        d=dt(r.get('date') or r.get('asOnDate') or r.get('as_on_date'))
        if d is not None and d.date()==pd.Timestamp('2026-06-30').date():return r
    return None


def local(tag):return tag.split('}')[-1].split(':')[-1]


def xroot(s,url):
    last=None
    for a in range(6):
        try:
            r=s.get(url,headers={**UA,'Referer':'https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern','Accept':'application/xml,text/xml,*/*'},timeout=40)
            if r.status_code in (401,403,500):
                try:s.get('https://www.nseindia.com/',timeout=15)
                except Exception:pass
                time.sleep(1+a*.6);continue
            r.raise_for_status();return ET.fromstring(r.content)
        except Exception as e:last=e;time.sleep(.7+a*.6)
    raise last or RuntimeError('shareholding_xbrl_failed')


def total_shares(root):
    candidates=[]
    for e in root.iter():
        if e.attrib.get('contextRef')!='ShareholdingPattern_ContextI':continue
        name=local(e.tag);txt=(e.text or '').strip()
        if name not in ('NumberOfShares','NumberOfFullyPaidUpEquityShares'):continue
        try:v=float(txt.replace(',',''))
        except Exception:continue
        if v>0:candidates.append((name,v,e.attrib.get('unitRef')))
    for preferred in ('NumberOfShares','NumberOfFullyPaidUpEquityShares'):
        vals=[x for x in candidates if x[0]==preferred]
        if vals:
            uniq={round(x[1],6) for x in vals}
            if len(uniq)!=1:raise ValueError('ambiguous_'+preferred)
            return vals[0]
    raise ValueError('aggregate_total_shares_missing')


def fnum(x):
    try:return float(str(x).replace(',','').replace('%','').strip())
    except Exception:return None


def decimals(x):
    s=str(x);return len(s.split('.',1)[1]) if '.' in s else 0


def interval(row,shares):
    mc=float(row['index_mcap_cr']);px=float(row['price']);n=float(shares)
    mh=.5*10**(-decimals(row['index_mcap_cr']));ph=.5*10**(-decimals(row['price']))
    point=mc*1e7/(px*n)
    lo=max(0,mc-mh)*1e7/((px+ph)*n)
    hi=(mc+mh)*1e7/(max(1e-12,px-ph)*n)
    return point,lo,hi


def main():
    s=session();weights,wmeta=weight_rows(s);done=[];errors=[]
    for row in weights:
        sym=row['symbol']
        try:
            jr=june(share_rows(s,sym))
            if not jr:raise ValueError('june_2026_shareholding_missing')
            url=jr.get('xbrl')
            if not url:raise ValueError('shareholding_xbrl_missing')
            tag,shares,unit=total_shares(xroot(s,url));pub=fnum(jr.get('public_val'));prom=fnum(jr.get('pr_and_prgrp'))
            if pub is None:raise ValueError('public_shareholding_missing')
            point,lo,hi=interval(row,shares);pubf=pub/100
            done.append({**row,'shareholding_total_shares':shares,'share_tag':tag,'share_unit':unit,'public_pct':pub,'promoter_pct':prom,'implied_iwf':point,'implied_iwf_min':lo,'implied_iwf_max':hi,'public_minus_iwf_pp':100*(pubf-point),'hard_upper_bound_breach':bool(lo>pubf),'xbrl':url})
        except Exception as e:errors.append({'symbol':sym,'error':f'{type(e).__name__}: {e}'})
        time.sleep(.18)
    done=sorted(done,key=lambda x:x['symbol']);breach=[x for x in done if x['hard_upper_bound_breach']]
    tot=sum(x['index_mcap_cr'] for x in done) or 1
    out={'schema_version':1,'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'research_only':True,'anchor_date':'2026-08-31','shareholding_quarter':'2026-06-30','weight_source':wmeta,'coverage':{'ok':len(done),'required':50,'failed':len(errors)},'failed':errors,'breaches':{'count':len(breach),'index_weight_pct':100*sum(x['index_mcap_cr'] for x in breach)/tot,'symbols':[x['symbol'] for x in breach]},'logic':'Public shareholding is only a hard upper bound. It is never substituted as free-float IWF. A breach is recorded only when the entire displayed-rounding interval for implied IWF exceeds official public shareholding.','constituents':done,'live_model_changed':False,'live_allocation_changed':False,'tolerances_changed':False}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print(json.dumps({'coverage':out['coverage'],'breaches':out['breaches'],'worst_gaps':sorted([{'symbol':x['symbol'],'gap_pp':x['public_minus_iwf_pp'],'weight_pct':x['published_weight_pct']} for x in done],key=lambda z:z['gap_pp'])[:12]},indent=2))

if __name__=='__main__':main()
