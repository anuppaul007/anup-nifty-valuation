#!/usr/bin/env python3
"""Update data/latest.json for Anup Nifty Valuation V2.

Design principles:
- Fetch after Indian market close; never expose source/API logic in the browser.
- Write atomically only after all mandatory NIFTY inputs validate.
- Keep last-known-good JSON if a source fails.
- Macro is a bounded tactical overlay. It does not redefine fundamental fair value.

NIFTY ratios/history: niftyindices.com through jugaad-data's current index helpers.
India 10y: FBIL par-yield table when available; FRED/OECD is the fallback (monthly/lagged).
Global macro: FRED CSV endpoints (no API key required for these public series).
"""
from __future__ import annotations
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
from io import StringIO
import json, math, re, sys
import numpy as np
import pandas as pd
import requests

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'latest.json'
UA={'User-Agent':'Mozilla/5.0 (compatible; AnupNiftyValuation/2.0; personal research dashboard)'}


def pick(d, aliases):
    if not isinstance(d,dict): return None
    norm={re.sub(r'[^a-z0-9]','',str(k).lower()):v for k,v in d.items()}
    for a in aliases:
        k=re.sub(r'[^a-z0-9]','',a.lower())
        if k in norm and norm[k] not in ('',None,'-'):
            return norm[k]
    return None

def fnum(x):
    if x is None: return None
    if isinstance(x,(int,float,np.number)):
        return float(x) if math.isfinite(float(x)) else None
    s=str(x).replace(',','').replace('%','').strip()
    try: v=float(s); return v if math.isfinite(v) else None
    except: return None

def pdate(x):
    if x is None: return None
    s=str(x).strip()
    for dayfirst in (True,False):
        try:
            t=pd.to_datetime(s,dayfirst=dayfirst,errors='raise')
            return t.date()
        except: pass
    return None

def fred(series):
    url=f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}'
    r=requests.get(url,headers=UA,timeout=30); r.raise_for_status()
    df=pd.read_csv(StringIO(r.text))
    df.columns=['date','value']
    df['date']=pd.to_datetime(df['date'],errors='coerce')
    df['value']=pd.to_numeric(df['value'],errors='coerce')
    return df.dropna().sort_values('date').reset_index(drop=True)

def robust_z(series, floor=1e-9):
    s=pd.Series(series).dropna()
    if len(s)<24: return 0.0
    look=s.tail(min(len(s),1260))
    mu=float(look.mean()); sd=float(look.std(ddof=0))
    if not math.isfinite(sd) or sd<floor: return 0.0
    return float(np.clip((float(s.iloc[-1])-mu)/sd,-3,3))

def pct_change_days(df, approx_days):
    s=df.set_index('date')['value'].sort_index()
    if len(s)<2: return None, pd.Series(dtype=float)
    lag=max(1,approx_days)
    ch=100*(s/s.shift(lag)-1)
    return (float(ch.dropna().iloc[-1]) if len(ch.dropna()) else None), ch.dropna()

def fetch_nifty():
    from jugaad_data.nse import index_raw, index_pe_raw
    end=date.today(); start=end-timedelta(days=5*365+45)
    ratio=index_pe_raw('NIFTY 50',start,end)
    price=index_raw('NIFTY 50',start,end)
    if not ratio or not price: raise RuntimeError('Nifty Indices returned no data')

    rr=[]
    for x in ratio:
        dt=pdate(pick(x,['Date','DATE','HistoricalDate']))
        pe=fnum(pick(x,['P/E','PE','pe']))
        pb=fnum(pick(x,['P/B','PB','pb']))
        dy=fnum(pick(x,['Div Yield %','Div Yield','Dividend Yield','DY','divYield']))
        if dt and pe and pb: rr.append({'date':dt,'pe':pe,'pb':pb,'dy':dy})
    pp=[]
    for x in price:
        dt=pdate(pick(x,['Date','DATE','HistoricalDate']))
        close=fnum(pick(x,['Close','CLOSE','Closing Index Value','Close Price']))
        if dt and close: pp.append({'date':dt,'level':close})
    if len(rr)<100 or len(pp)<100: raise RuntimeError(f'Parsed too little NIFTY data: ratios={len(rr)}, prices={len(pp)}')
    rdf=pd.DataFrame(rr).drop_duplicates('date').set_index('date').sort_index()
    pdf=pd.DataFrame(pp).drop_duplicates('date').set_index('date').sort_index()
    d=rdf.join(pdf,how='inner').dropna(subset=['pe','pb','level'])
    if len(d)<100: raise RuntimeError('Unable to align NIFTY ratio and price histories')
    latest=d.iloc[-1]
    latest_date=d.index[-1]

    # Month-end sample. Preserve only consolidated-earnings era in the auto feed.
    md=d[d.index>=date(2021,5,1)].copy()
    md.index=pd.to_datetime(md.index)
    m=md.groupby(md.index.to_period('M')).tail(1)
    hist=[[idx.strftime('%Y-%m'),round(float(row.pe),4),round(float(row.pb),4),None if pd.isna(row.dy) else round(float(row.dy),4)] for idx,row in m.iterrows()]

    eps=(d['level']/d['pe']).copy()
    eps.index=pd.to_datetime(eps.index)
    em=eps.groupby(eps.index.to_period('M')).last().sort_index()
    g12=100*(em/em.shift(12)-1)
    accel=g12-g12.shift(6)
    zg=robust_z(g12,3.0); za=robust_z(accel,3.0)
    escore=float(np.tanh((0.7*zg+0.3*za)/1.5))
    return {
      'latest':{'date':latest_date.isoformat(),'level':float(latest.level),'pe':float(latest.pe),'pb':float(latest.pb),'div_yield':None if pd.isna(latest.dy) else float(latest.dy)},
      'history':hist,
      'earnings':{'eps':float(eps.iloc[-1]),'eps_growth_12m':None if pd.isna(g12.iloc[-1]) else float(g12.iloc[-1]),'acceleration_6m':None if pd.isna(accel.iloc[-1]) else float(accel.iloc[-1]),'score':escore}
    }

def fetch_india_gsec10():
    # Prefer FBIL daily par yield. For a public/commercial product, review FBIL redistribution terms.
    try:
        html=requests.get('https://www.fbil.org.in/',headers=UA,timeout=30).text
        tables=pd.read_html(StringIO(html))
        candidates=[]
        for t in tables:
            cols=[str(c).strip().lower() for c in t.columns]
            if any('tenor' in c for c in cols) and any('rate' in c for c in cols):
                t.columns=cols
                tc=next(c for c in cols if 'tenor' in c)
                rc=next(c for c in cols if 'rate' in c)
                rows=t[t[tc].astype(str).str.upper().str.replace(' ','').eq('10YR')]
                for _,r in rows.iterrows():
                    v=fnum(r[rc])
                    if v and 3<v<15: candidates.append(v)
        if candidates: return float(candidates[0]),'FBIL daily par yield'
    except Exception as e:
        print('FBIL fallback:',e,file=sys.stderr)
    df=fred('INDIRLTLT01STM')
    return float(df.value.iloc[-1]),'FRED/OECD monthly 10-year benchmark (lagged fallback)'

def macro_data():
    real=fred('DFII10')
    usd=fred('DTWEXBGS')
    oil=fred('DCOILBRENTEU')
    fed=fred('WALCL')
    vix=fred('VIXCLS')
    usd3,usd3s=pct_change_days(usd,63)
    oil3,oil3s=pct_change_days(oil,63)
    fed6,fed6s=pct_change_days(fed,26)  # weekly observations ~6 months
    # Supportive-for-equity sign convention.
    z_real=robust_z(real.value,0.15)
    z_usd=robust_z(usd3s,0.5)
    z_oil=robust_z(oil3s,1.0)
    z_fed=robust_z(fed6s,0.5)
    raw=(-0.35*z_real -0.25*z_usd -0.25*z_oil +0.15*z_fed)
    score=float(np.tanh(raw/1.5))
    return {
      'us_real_10y':float(real.value.iloc[-1]),
      'usd_3m_pct':usd3,
      'brent_3m_pct':oil3,
      'fed_assets_6m_pct':fed6,
      'vix':float(vix.value.iloc[-1]),
      'score':score
    }

def main():
    n=fetch_nifty()
    g10,gsrc=fetch_india_gsec10()
    mac=macro_data()
    latest=n['latest']; latest['gsec10']=g10
    mandatory=[latest.get(k) for k in ['level','pe','pb','div_yield','gsec10']]
    if any(v is None or not math.isfinite(float(v)) or float(v)<=0 for v in mandatory):
        raise RuntimeError('Mandatory input failed validation; retaining old JSON')
    # Confidence is deliberately separate from direction; high VIX reduces confidence/deployment speed.
    vix=mac.get('vix') or 20
    confidence=float(np.clip(1-max(0,vix-18)/40,0.35,1.0))
    out={
      'generated_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
      'nifty':latest,
      'earnings':n['earnings'],
      'macro':mac,
      'confidence':confidence,
      'history':n['history'],
      'sources':[
        {'name':'Nifty Indices / NSE','role':'NIFTY 50 level, P/E, P/B and dividend yield'},
        {'name':gsrc,'role':'India 10-year government bond yield'},
        {'name':'FRED','role':'US real yield, broad USD, Brent, Federal Reserve assets and VIX'}
      ]
    }
    tmp=OUT.with_suffix('.tmp')
    tmp.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8')
    tmp.replace(OUT)
    print(f'Updated {OUT} for NIFTY date {latest["date"]}')

if __name__=='__main__':
    main()
