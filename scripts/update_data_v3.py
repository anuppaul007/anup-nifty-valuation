#!/usr/bin/env python3
from datetime import datetime,timezone
from io import StringIO
import json,math,time
import numpy as np
import pandas as pd
import requests
from pathlib import Path
import update_data as b
import macro_v3
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data'/'latest.json'
UA={'User-Agent':'Mozilla/5.0 (compatible; AnupNiftyValuation/3.0; personal research dashboard)'}

def fred_retry(series):
    url=f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}';err=None
    for timeout in (30,60,90):
        try:
            r=requests.get(url,headers=UA,timeout=timeout);r.raise_for_status();df=pd.read_csv(StringIO(r.text));df.columns=['date','value'];df['date']=pd.to_datetime(df['date'],errors='coerce');df['value']=pd.to_numeric(df['value'],errors='coerce');q=df.dropna().sort_values('date').reset_index(drop=True)
            if len(q):return q
        except Exception as e:err=e;time.sleep(2)
    raise RuntimeError(f'FRED {series} unavailable after retries: {err}')

# Replace the V2 single-attempt FRED helper everywhere, including macro_v3's shared module reference.
b.fred=fred_retry

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
        mac,cal=macro_v3.build(g10,latest,n['history'],old);macro_stale=False
    except Exception as e:
        prior=old.get('macro')
        if not prior:raise
        mac=prior;cal=old.get('calibration') or {};macro_stale=True;print('Macro refresh failed; retained last-known-good macro:',e)
    vix=mac.get('vix') or 20;vconf=float(np.clip(1-max(0,vix-18)/40,.35,1));coverage=float(np.clip(mac.get('active_block_weight',0),.45,1));confidence=float(np.clip(vconf*(.75+.25*coverage),.30,1))
    out={'generated_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'model_version':'3.0','macro_stale':macro_stale,'nifty':latest,'earnings':n['earnings'],'macro':mac,'confidence':confidence,'history':n['history'],'calibration':cal,'sources':[{'name':'Nifty Indices / NSE','role':'NIFTY 50 level, P/E, P/B and dividend yield'},{'name':gsrc,'role':'India 10-year government bond yield'},{'name':'FRED / Federal Reserve / BIS / OECD','role':'US yields, broad USD, Brent, Fed assets, VIX, India REER and yield-spread history'},{'name':'STOXX','role':'Emerging Markets ex-India relative valuation fundamentals'},{'name':'National Bureau of Statistics of China','role':'Official China manufacturing PMI / new orders'},{'name':'CCIL (best effort)','role':'USD/INR 1-month forward implied rate differential; excluded from score until calibrated'}]}
    tmp=OUT.with_suffix('.tmp');tmp.write_text(json.dumps(out,indent=2,allow_nan=False));tmp.replace(OUT);print(f'Updated V3 for NIFTY {latest["date"]}; macro={mac["score"]:.3f}; stale={macro_stale}')
if __name__=='__main__':main()
