#!/usr/bin/env python3
from datetime import datetime,timezone,date
from io import StringIO
import json,math,time
import numpy as np
import pandas as pd
import requests
from pathlib import Path
import update_data as b
import macro_v3
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data'/'latest.json'
UA={'User-Agent':'Mozilla/5.0 (compatible; AnupNiftyValuation/3.2; personal research dashboard)'}

# Hard network cap: an optional provider must never hold the whole refresh hostage.
_real_get=requests.get
def capped_get(*args,**kwargs):
    t=kwargs.get('timeout',8)
    try:t=min(float(t),8.0)
    except:t=8.0
    kwargs['timeout']=t
    return _real_get(*args,**kwargs)
requests.get=capped_get
b.requests.get=capped_get
macro_v3.requests.get=capped_get

def fred_retry(series):
    # FRED is secondary in V3.2: one short attempt, then other factors continue.
    url=f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}&cosd=2015-01-01'
    try:
        r=capped_get(url,headers=UA,timeout=8);r.raise_for_status();df=pd.read_csv(StringIO(r.text));df.columns=['date','value'];df['date']=pd.to_datetime(df['date'],errors='coerce');df['value']=pd.to_numeric(df['value'],errors='coerce');q=df.dropna().sort_values('date').reset_index(drop=True)
        if len(q):return q
    except Exception as e:raise RuntimeError(f'FRED {series} unavailable: {e}')
    raise RuntimeError(f'FRED {series} empty')
b.fred=fred_retry

# Current-only STOXX path. Historical archive backfill is deliberately deferred to a
# separate future job so it cannot delay the daily market refresh.
def relative_em_fast(nifty,hist,old):
    prior=(((old or {}).get('calibration') or {}).get('em_ex_india_history') or [])
    hh=[x for x in prior if isinstance(x,dict) and x.get('month')][-60:]
    cur=macro_v3.safe('STOXX current',macro_v3.stoxx)
    out={'available':bool(cur),'history_count':len(hh),'score':None}
    if cur:
        rel=.6*math.log(nifty['pe']/cur['pe'])+.4*math.log(nifty['pb']/cur['pb'])
        z=macro_v3.zhist(rel,[x.get('relative_log_premium') for x in hh],12,.03)
        out.update({'em_ex_india_pe':cur['pe'],'em_ex_india_pb':cur['pb'],'em_ex_india_div_yield':cur['div_yield'],'asof':cur.get('asof'),'nifty_pe_premium_pct':100*(nifty['pe']/cur['pe']-1),'nifty_pb_premium_pct':100*(nifty['pb']/cur['pb']-1),'relative_log_premium':rel,'z':z,'score':None if z is None else macro_v3.squash(-z)})
        mon=date.today().strftime('%Y-%m');hh=[x for x in hh if x.get('month')!=mon];hh.append({'month':mon,'em_pe':cur['pe'],'em_pb':cur['pb'],'nifty_pe':nifty['pe'],'nifty_pb':nifty['pb'],'relative_log_premium':rel})
    return out,hh[-60:]
macro_v3.relative_em=relative_em_fast

def main():
    try:old=json.loads(OUT.read_text()) if OUT.exists() else {}
    except:old={}
    n=b.fetch_nifty()
    try:g10,gsrc=b.fetch_india_gsec10()
    except Exception as e:
        prior=((old.get('nifty') or {}).get('gsec10'))
        if prior is None:raise
        g10=float(prior);gsrc=f'Last-known-good India 10Y (live source unavailable: {type(e).__name__})'
    latest=n['latest'];latest['gsec10']=g10
    vals=[latest.get(k) for k in ['level','pe','pb','div_yield','gsec10']]
    if any(v is None or not math.isfinite(float(v)) or float(v)<=0 for v in vals):raise RuntimeError('Mandatory input validation failed; keeping old JSON')

    try:
        mac,cal=macro_v3.build(g10,latest,n['history'],old)
    except Exception as e:
        prior=old.get('macro')
        if not prior:raise
        mac=prior;cal=old.get('calibration') or {};mac['stale_factors']=list(set((mac.get('stale_factors') or [])+['macro build failure']))
        print('Macro build exception; retained last-known-good macro:',e)

    coverage=float(np.clip(mac.get('active_block_weight',0),0,1))
    macro_stale=coverage<0.30
    macro_partial=bool(mac.get('stale_factors')) or coverage<0.99
    vix=mac.get('vix') or 20
    vconf=float(np.clip(1-max(0,vix-18)/40,.35,1))
    confidence=float(np.clip(vconf*(.65+.35*coverage),.30,1))

    out={'generated_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'model_version':'3.2','macro_stale':macro_stale,'macro_partial':macro_partial,'nifty':latest,'earnings':n['earnings'],'macro':mac,'confidence':confidence,'history':n['history'],'calibration':cal,'sources':[
        {'name':'Nifty Indices / NSE','role':'NIFTY 50 level, P/E, P/B and dividend yield'},
        {'name':gsrc,'role':'India 10-year government bond yield'},
        {'name':'U.S. Treasury','role':'US 10-year real and nominal Treasury yields'},
        {'name':'Federal Reserve H.10 / H.4.1','role':'Broad USD index and Federal Reserve balance-sheet assets'},
        {'name':'CBOE','role':'VIX; confidence/deployment speed only'},
        {'name':'Yahoo Finance / ICE-linked market data','role':'Brent futures history used for oil momentum'},
        {'name':'BIS / FRED (secondary)','role':'India REER and selected historical calibration series'},
        {'name':'STOXX','role':'Emerging Markets ex-India relative valuation when available'},
        {'name':'National Bureau of Statistics of China','role':'Official China manufacturing PMI / new orders when available'},
        {'name':'CCIL (best effort)','role':'USD/INR 1-month forward premium; excluded until calibrated'}]}
    tmp=OUT.with_suffix('.tmp');tmp.write_text(json.dumps(out,indent=2,allow_nan=False));tmp.replace(OUT)
    print(f'Updated V3.2 for NIFTY {latest["date"]}; macro={mac.get("score",0):.3f}; coverage={coverage:.0%}; partial={macro_partial}')
if __name__=='__main__':main()
