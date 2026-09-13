#!/usr/bin/env python3
"""V8 gate 1: independently verify the official NIFTY 50 valuation benchmark.

This calls Nifty Indices' P/E-P/B-Dividend Yield historical endpoint directly
and compares it with the maintained `jugaad_data.index_pe_raw` wrapper. It does
not reconstruct any constituent and does not modify the live model.

The gate fails if:
* the direct official endpoint does not return the requested 31-Aug-2026 row;
* the returned row cannot be parsed as PE/PB/DY;
* the direct official values disagree with the helper values beyond display
  precision (1e-9 after numeric conversion).
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from pathlib import Path
import json, math, requests

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'current_definition_v8_benchmark.json'
ANCHOR=date(2026,8,31)
SYMBOL='NIFTY 50'
URL='https://niftyindices.com/BackPage/getpepbHistoricaldataDBtoString'

HEADERS={
 'Accept':'application/json, text/javascript, */*; q=0.01',
 'Content-Type':'application/json; charset=UTF-8',
 'Origin':'https://niftyindices.com',
 'Referer':'https://niftyindices.com/reports/historical-data',
 'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36',
 'X-Requested-With':'XMLHttpRequest',
}


def fnum(x):
    if x in (None,'','-'):return None
    try:return float(str(x).replace(',','').replace('%','').strip())
    except Exception:return None


def values(row):
    # The official endpoint has historically used lower-case pe/pb/divYield,
    # while wrappers and mirrors may expose display-key variants. Parse only
    # known semantic aliases; never infer by field order.
    aliases={
      'pe':['pe','PE','P/E','p_e'],
      'pb':['pb','PB','P/B','p_b'],
      'dy':['divYield','Div Yield','Div Yield %','Dividend Yield','DY','dy'],
    }
    out={}
    for k,names in aliases.items():
        v=None
        for n in names:
            if n in row:
                v=fnum(row.get(n))
                if v is not None:break
        out[k]=v
    return out


def row_date(row):
    for k in ('DATE','Date','date','HistoricalDate'):
        if row.get(k):return str(row.get(k))
    return None


def direct():
    cinfo={'name':SYMBOL,'startDate':ANCHOR.strftime('%d-%b-%Y'),'endDate':ANCHOR.strftime('%d-%b-%Y'),'indexName':SYMBOL}
    payload={'cinfo':str(cinfo).replace('"',"'")}
    s=requests.Session();s.headers.update(HEADERS)
    # Seed first-party cookies but do not depend on a cached helper response.
    try:s.get('https://niftyindices.com/reports/historical-data',timeout=20)
    except Exception:pass
    r=s.post(URL,json=payload,headers=HEADERS,timeout=40);r.raise_for_status()
    raw=r.json()
    if isinstance(raw,dict) and 'd' in raw:raw=raw['d']
    if isinstance(raw,str):raw=json.loads(raw)
    if not isinstance(raw,list) or not raw:raise RuntimeError('official_endpoint_empty')
    # Exact one-day request should normally return one row. If more are returned,
    # retain only rows whose date text identifies 31-Aug-2026.
    exact=[]
    for x in raw:
        ds=(row_date(x) or '').upper().replace(' ','')
        if any(t in ds for t in ('31-AUG-2026','31-AUG-26','31/08/2026','31-08-2026','2026-08-31')):exact.append(x)
    row=exact[0] if exact else raw[0] if len(raw)==1 else None
    if row is None:raise RuntimeError('official_anchor_row_ambiguous')
    vals=values(row)
    if not all(math.isfinite(float(vals[k])) for k in ('pe','pb','dy') if vals[k] is not None) or any(vals[k] is None for k in ('pe','pb','dy')):
        raise RuntimeError('official_ratio_parse_failed')
    return {'payload':payload,'http_status':r.status_code,'raw_row':row,'values':vals}


def helper():
    from jugaad_data.nse import index_pe_raw
    rows=index_pe_raw(SYMBOL,ANCHOR,ANCHOR) or []
    if not rows:raise RuntimeError('helper_empty')
    row=rows[0];vals=values(row)
    if any(vals[k] is None for k in ('pe','pb','dy')):raise RuntimeError('helper_ratio_parse_failed')
    return {'raw_row':row,'values':vals}


def main():
    d=direct();h=helper();delta={k:float(d['values'][k])-float(h['values'][k]) for k in ('pe','pb','dy')}
    agrees=all(abs(v)<=1e-9 for v in delta.values())
    if not agrees:raise RuntimeError('direct_official_and_helper_disagree: '+json.dumps(delta))
    out={
      'schema_version':1,'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
      'research_only':True,'anchor_date':ANCHOR.isoformat(),'symbol':SYMBOL,
      'official_endpoint':URL,'direct':d,'helper':h,'delta':delta,'agrees':agrees,
      'verified_benchmark':d['values'],
      'interpretation':'This validates only the published comparison target. It does not validate any constituent reconstruction formula.',
      'live_model_changed':False,'live_allocation_changed':False,'tolerances_changed':False,
    }
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print(json.dumps({'verified_benchmark':out['verified_benchmark'],'delta':delta,'agrees':agrees},indent=2))

if __name__=='__main__':main()
