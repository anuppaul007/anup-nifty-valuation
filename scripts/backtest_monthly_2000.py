#!/usr/bin/env python3
"""Monthly long-history allocation table, January 2000 onward.

Purpose
-------
Generate exactly one observation per calendar month using the first NIFTY 50
trading day available in that month. Output is intentionally simple: Date,
Equity %, Debt %.

Important scope
---------------
This is a *valuation-core* historical reconstruction using the live V3.6 fixed
valuation references and live allocation curve (k=1.35, zc=2.5). It does NOT
silently neutral-fill the V3.6 macro overlay, because several macro series do
not exist consistently back to 2000. India long-term yield uses the prior
calendar month's monthly observation to avoid same-month look-ahead.

Pre-31-Mar-2021 NSE index P/E history was calculated under the older standalone
earnings methodology, while the current index P/E uses consolidated trailing
financials where available. Therefore 2000-2021 results are a mechanical
historical sensitivity series, not directly methodology-comparable to current
V3.6 readings.
"""
from __future__ import annotations
from datetime import date
from pathlib import Path
from io import StringIO
import json, math
import numpy as np
import pandas as pd
import update_data as b
import macro_v3 as m

ROOT=Path(__file__).resolve().parents[1]
CSV_OUT=ROOT/'data'/'backtest_monthly_2000.csv'
JSON_OUT=ROOT/'data'/'backtest_monthly_2000.json'
START=date(2000,1,1)
LIVE_K=1.35
LIVE_ZC=2.5
C={'peM':22.44,'peS':2.08,'pbM':3.88,'pbS':.45,'roeM':17.36,'roeS':1.92,
   'dyM':1.25,'dyS':.18,'gapM':-2.60,'gapS':.70,'beta':.60}


def finite(x):
    try:return x is not None and math.isfinite(float(x))
    except (TypeError,ValueError):return False

def clip(x,a,b):return max(a,min(b,float(x)))
def curve(z,k=LIVE_K,zc=LIVE_ZC):
    f=lambda x:100/(1+math.exp(float(k)*x));lo=f(zc);hi=f(-zc)
    return clip((f(float(z))-lo)/(hi-lo)*100,0,100)

def valuation_z(pe,pb,dy,gsec):
    pe,pb,dy,gsec=map(float,(pe,pb,dy,gsec));roe=100*pb/pe;gap=100/pe-gsec
    lenses=[
      ((pe-C['peM'])/C['peS'],30),
      ((pb-C['pbM'])/C['pbS']-C['beta']*(roe-C['roeM'])/C['roeS'],25),
      (-(gap-C['gapM'])/C['gapS'],30),
      (-(dy-C['dyM'])/C['dyS'],10),
    ]
    return sum(v*w for v,w in lenses)/sum(w for _,w in lenses)

def fetch_ratio_first_days():
    from jugaad_data.nse import index_pe_raw
    end=date.today();rows=index_pe_raw('NIFTY 50',START,end)
    parsed=[]
    for x in rows or []:
        dt=b.pdate(b.pick(x,['Date','DATE','HistoricalDate']))
        pe=b.fnum(b.pick(x,['P/E','PE','pe']));pb=b.fnum(b.pick(x,['P/B','PB','pb']));dy=b.fnum(b.pick(x,['Div Yield %','Div Yield','Dividend Yield','DY','divYield']))
        if dt and START<=dt<=end and all(finite(v) and float(v)>0 for v in (pe,pb,dy)):
            parsed.append((pd.Timestamp(dt),float(pe),float(pb),float(dy)))
    if not parsed:raise RuntimeError('No NIFTY 50 valuation history returned')
    q=pd.DataFrame(parsed,columns=['trading_date','pe','pb','dy']).drop_duplicates('trading_date').sort_values('trading_date')
    q['month']=q.trading_date.dt.to_period('M')
    q=q.groupby('month',as_index=False).first()
    return q

def fetch_india_long_yield():
    # FRED mirrors the OECD monthly India long-term government bond series and
    # provides the long history needed here. Use only the PRIOR month at each
    # signal date so the current month's monthly average is never used early.
    try:
        y=b.fred('INDIRLTLT01STM')
        y=y[['date','value']].copy();y['date']=pd.to_datetime(y['date']);y['value']=pd.to_numeric(y['value'],errors='coerce')
        y=y.dropna();y['month']=y.date.dt.to_period('M');s=y.groupby('month').value.last().sort_index()
        if len(s)>=120:return s,'FRED/OECD India long-term government bond yield'
    except Exception:
        pass
    # Direct OECD fallback with an earlier requested start date.
    url=('https://sdmx.oecd.org/public/rest/data/'
         'OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0/IND.M.IRLT.PA.....'
         '?startPeriod=1999-01&dimensionAtObservation=AllDimensions&format=csvfile')
    y=m._sdmx_csv(url,url);y['month']=pd.to_datetime(y.date).dt.to_period('M');s=y.groupby('month').value.last().sort_index()
    return s,'OECD Data Explorer India long-term government bond yield'

def build():
    ratios=fetch_ratio_first_days();ys,ysource=fetch_india_long_yield();ys=ys.shift(1)
    rows=[]
    for _,r in ratios.iterrows():
        month=r['month'];gsec=ys.get(month,np.nan)
        if not finite(gsec):continue
        z=valuation_z(r.pe,r.pb,r.dy,gsec);equity=curve(z);eq_int=int(round(equity));eq_int=max(0,min(100,eq_int))
        rows.append({'Date':str(month.start_time.date()),'Equity %':eq_int,'Debt %':100-eq_int,
                     '_TradingDate':str(r.trading_date.date()),'_z':float(z),'_pe':float(r.pe),'_pb':float(r.pb),'_dy':float(r.dy),'_gsec_prior_month':float(gsec)})
    if not rows:raise RuntimeError('No complete monthly observations after yield alignment')
    out=pd.DataFrame(rows)
    # Jan-2000 through current month should be represented whenever source data exist.
    expected=pd.period_range('2000-01',pd.Period(date.today(),freq='M'),freq='M')
    observed=pd.PeriodIndex(pd.to_datetime(out['Date']).dt.to_period('M'))
    missing=[str(x) for x in expected if x not in observed]
    public=out[['Date','Equity %','Debt %']].copy()
    public.to_csv(CSV_OUT,index=False)
    meta={
      'status':'complete' if not missing else 'partial','model_version':'3.6','scope':'valuation core only; macro and earnings overlays excluded',
      'start':public.Date.iloc[0],'end':public.Date.iloc[-1],'rows':int(len(public)),'missing_months':missing,
      'signal_rule':'first available NIFTY 50 trading day in each calendar month; displayed Date is the calendar month first day',
      'india_yield_rule':'prior calendar month monthly long-term government yield; avoids same-month look-ahead','india_yield_source':ysource,
      'live_parameters':{'curve_slope_k':LIVE_K,'extreme_threshold_zc':LIVE_ZC,'references':C},
      'methodology_warning':'Pre-31-Mar-2021 NIFTY P/E history used the older standalone-earnings methodology; current methodology uses consolidated trailing earnings where available. Pre-2021 rows are therefore a mechanical sensitivity series, not directly comparable to current V3.6 valuation levels.',
      'rows_data':public.to_dict(orient='records')
    }
    JSON_OUT.write_text(json.dumps(meta,indent=2,allow_nan=False),encoding='utf-8')
    return meta

if __name__=='__main__':
    try:
        x=build();print(json.dumps({'status':x['status'],'rows':x['rows'],'start':x['start'],'end':x['end'],'missing_months':x['missing_months']}))
    except Exception as e:
        error={'status':'unavailable','error':f'{type(e).__name__}: {e}'};JSON_OUT.write_text(json.dumps(error,indent=2),encoding='utf-8');print(json.dumps(error));raise
