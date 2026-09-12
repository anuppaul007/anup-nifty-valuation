#!/usr/bin/env python3
"""Monthly long-history allocation table, January 2000 onward.

Generates one observation per calendar month using the first available NIFTY 50
trading day of that month, while displaying the date as the first calendar day.
Public output is intentionally only: Date, Equity %, Debt %.

For a genuinely continuous 2000-present reconstruction, this study uses only
the valuation lenses that exist across the full history: P/E (30%),
profitability-adjusted P/B (25%) and dividend yield (10%), renormalised across
those 65 weight points. The live V3.6 allocation curve itself remains unchanged
(k=1.35, zc=2.5). The India-yield lens, earnings overlay and macro overlay are
excluded for the ENTIRE backtest rather than being silently neutral-filled or
switched on part-way through history.

Pre-31-Mar-2021 NSE index P/E history used the older standalone-earnings
methodology, while the current index P/E uses consolidated trailing financials
where available. Thus the pre-2021 rows are a mechanical historical sensitivity
series, not directly methodology-comparable to current V3.6 readings.
"""
from __future__ import annotations
from datetime import date
from pathlib import Path
import json, math
import pandas as pd
import update_data as b

ROOT=Path(__file__).resolve().parents[1]
CSV_OUT=ROOT/'data'/'backtest_monthly_2000.csv'
JSON_OUT=ROOT/'data'/'backtest_monthly_2000.json'
START=date(2000,1,1)
LIVE_K=1.35
LIVE_ZC=2.5
C={'peM':22.44,'peS':2.08,'pbM':3.88,'pbS':.45,'roeM':17.36,'roeS':1.92,
   'dyM':1.25,'dyS':.18,'beta':.60}


def finite(x):
    try:return x is not None and math.isfinite(float(x))
    except (TypeError,ValueError):return False

def clip(x,a,b):return max(a,min(b,float(x)))
def curve(z,k=LIVE_K,zc=LIVE_ZC):
    f=lambda x:100/(1+math.exp(float(k)*x));lo=f(zc);hi=f(-zc)
    return clip((f(float(z))-lo)/(hi-lo)*100,0,100)

def valuation_z(pe,pb,dy):
    pe,pb,dy=map(float,(pe,pb,dy));roe=100*pb/pe
    lenses=[
      ((pe-C['peM'])/C['peS'],30),
      ((pb-C['pbM'])/C['pbS']-C['beta']*(roe-C['roeM'])/C['roeS'],25),
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
    return q.groupby('month',as_index=False).first()

def build():
    ratios=fetch_ratio_first_days();rows=[]
    for _,r in ratios.iterrows():
        month=r['month'];z=valuation_z(r.pe,r.pb,r.dy);equity=curve(z);eq_int=max(0,min(100,int(round(equity))))
        rows.append({'Date':str(month.start_time.date()),'Equity %':eq_int,'Debt %':100-eq_int})
    if not rows:raise RuntimeError('No complete monthly NIFTY valuation observations')
    public=pd.DataFrame(rows)
    expected=pd.period_range('2000-01',pd.Period(date.today(),freq='M'),freq='M')
    observed=pd.PeriodIndex(pd.to_datetime(public['Date']).dt.to_period('M'))
    missing=[str(x) for x in expected if x not in observed]
    public.to_csv(CSV_OUT,index=False)
    meta={
      'status':'complete' if not missing else 'partial','model_version':'3.6-long-history-common-lens',
      'scope':'common-factor valuation backtest only; P/E + profitability-adjusted P/B + dividend yield. Yield-gap, earnings and macro overlays excluded for the entire 2000-present series.',
      'start':public.Date.iloc[0],'end':public.Date.iloc[-1],'rows':int(len(public)),'missing_months':missing,
      'signal_rule':'first available NIFTY 50 trading day in each calendar month; displayed Date is the calendar month first day',
      'factor_weights':{'pe':30,'profitability_adjusted_pb':25,'dividend_yield':10},
      'live_curve_parameters':{'curve_slope_k':LIVE_K,'extreme_threshold_zc':LIVE_ZC},
      'reference_constants':C,
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
