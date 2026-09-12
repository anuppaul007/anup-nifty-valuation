#!/usr/bin/env python3
"""Monthly long-history allocation table, January 2000 onward.

Generates one observation per calendar month using the first available NIFTY 50
trading day of that month, while displaying the date as the first calendar day.
Public output columns are: Date, NIFTY 50, RBI Repo Rate %, Equity %, Debt %.

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

RBI rate convention: the repo/policy rate in force on the displayed calendar
first day. Before the June-2000 LAF series, the then fixed repo rate is used.
RBI/Reuters note that before 29-Oct-2004 the repo/reverse-repo nomenclature was
opposite to current international usage; the historical policy-rate series is
kept on the current-comparable convention used by RBI/Reuters timelines.
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

# Effective-date history of the RBI repo/policy rate. June-2000 onward follows
# the RBI/Reuters historical policy-rate timeline. Jan-May 2000 uses the fixed
# repo rate then in force (6%, cut to 5% effective 03-Apr-2000).
REPO_CHANGES=[
 ('1999-03-01',6.00),('2000-04-03',5.00),('2000-06-05',9.05),('2000-06-07',9.00),('2000-06-09',9.05),('2000-06-12',9.25),('2000-06-13',9.55),('2000-06-14',10.85),('2000-06-19',13.50),('2000-06-20',14.00),('2000-06-21',13.50),('2000-06-22',13.00),('2000-06-23',13.05),('2000-06-27',12.60),('2000-06-28',12.25),('2000-07-13',9.00),('2000-07-21',10.00),('2000-08-09',16.00),('2000-08-30',15.00),('2000-09-06',13.50),('2000-10-13',10.25),('2000-11-06',10.00),
 ('2001-03-09',9.00),('2001-04-30',8.75),('2001-06-07',8.50),('2002-03-28',8.00),('2002-11-12',7.50),('2003-03-07',7.10),('2003-03-19',7.00),('2004-03-31',6.00),('2005-10-26',6.25),('2006-01-24',6.50),('2006-06-08',6.75),('2006-07-25',7.00),('2006-10-30',7.25),('2007-01-31',7.50),('2007-03-30',7.75),('2008-06-11',8.00),('2008-06-24',8.50),('2008-07-29',9.00),('2008-10-20',8.00),('2008-11-03',7.50),('2008-12-08',6.50),('2009-01-02',5.50),('2009-03-04',5.00),('2009-04-21',4.75),
 ('2010-03-19',5.00),('2010-04-20',5.25),('2010-07-02',5.50),('2010-07-27',5.75),('2010-09-16',6.00),('2010-11-02',6.25),('2011-01-25',6.50),('2011-03-17',6.75),('2011-05-03',7.25),('2011-06-16',7.50),('2011-07-26',8.00),('2011-09-16',8.25),('2011-10-25',8.50),('2012-04-17',8.00),('2013-01-29',7.75),('2013-03-19',7.50),('2013-05-03',7.25),('2013-09-20',7.50),('2013-10-29',7.75),('2014-01-28',8.00),('2015-01-15',7.75),('2015-03-04',7.50),('2015-06-02',7.25),('2015-09-29',6.75),('2016-04-05',6.50),('2016-10-04',6.25),('2017-08-02',6.00),('2018-06-06',6.25),('2018-08-01',6.50),('2019-02-07',6.25),('2019-04-04',6.00),('2019-06-06',5.75),('2019-08-07',5.40),('2019-10-04',5.15),('2020-03-27',4.40),('2020-05-22',4.00),('2022-05-04',4.40),('2022-06-08',4.90),('2022-08-05',5.40),('2022-09-30',5.90),('2022-12-07',6.25),('2023-02-08',6.50),('2025-02-07',6.25),('2025-04-09',6.00),('2025-06-06',5.50),('2025-12-05',5.25)
]
REPO_CHANGES=[(pd.Timestamp(d),float(r)) for d,r in REPO_CHANGES]


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

def repo_on(dt):
    dt=pd.Timestamp(dt);eligible=[r for d,r in REPO_CHANGES if d<=dt]
    return eligible[-1] if eligible else None

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

def fetch_nifty_first_days():
    from jugaad_data.nse import index_raw
    end=date.today();rows=index_raw('NIFTY 50',START,end)
    parsed=[]
    for x in rows or []:
        dt=b.pdate(b.pick(x,['Date','DATE','HistoricalDate','Index Date']))
        level=b.fnum(b.pick(x,['CLOSE','Close','Closing Index Value','Index Value','INDEX_VALUE','close']))
        if dt and START<=dt<=end and finite(level) and float(level)>0:parsed.append((pd.Timestamp(dt),float(level)))
    if not parsed:raise RuntimeError('No NIFTY 50 price history returned')
    q=pd.DataFrame(parsed,columns=['market_date','nifty50']).drop_duplicates('market_date').sort_values('market_date');q['month']=q.market_date.dt.to_period('M')
    return q.groupby('month',as_index=False).first()

def build():
    ratios=fetch_ratio_first_days();prices=fetch_nifty_first_days();q=ratios.merge(prices,on='month',how='left');rows=[]
    for _,r in q.iterrows():
        month=r['month'];z=valuation_z(r.pe,r.pb,r.dy);equity=curve(z);eq_int=max(0,min(100,int(round(equity))));cal_date=month.start_time
        rows.append({'Date':str(cal_date.date()),'NIFTY 50':round(float(r.nifty50),2) if finite(r.nifty50) else None,'RBI Repo Rate %':repo_on(cal_date),'Equity %':eq_int,'Debt %':100-eq_int})
    if not rows:raise RuntimeError('No complete monthly NIFTY valuation observations')
    public=pd.DataFrame(rows)
    expected=pd.period_range('2000-01',pd.Period(date.today(),freq='M'),freq='M');observed=pd.PeriodIndex(pd.to_datetime(public['Date']).dt.to_period('M'));missing=[str(x) for x in expected if x not in observed]
    if public['NIFTY 50'].isna().any():raise RuntimeError('Missing NIFTY 50 level for one or more months')
    public.to_csv(CSV_OUT,index=False)
    meta={'status':'complete' if not missing else 'partial','model_version':'3.6-long-history-common-lens','scope':'common-factor valuation backtest only; P/E + profitability-adjusted P/B + dividend yield. Yield-gap, earnings and macro overlays excluded for the entire 2000-present series.','start':public.Date.iloc[0],'end':public.Date.iloc[-1],'rows':int(len(public)),'missing_months':missing,'signal_rule':'first available NIFTY 50 trading day in each calendar month; displayed Date is the calendar month first day','nifty_column_rule':'NIFTY 50 close on the first available trading day of each month','rbi_rate_rule':'RBI repo/policy rate in force on the displayed calendar first day; Jan-May 2000 uses the fixed repo rate then in force','factor_weights':{'pe':30,'profitability_adjusted_pb':25,'dividend_yield':10},'live_curve_parameters':{'curve_slope_k':LIVE_K,'extreme_threshold_zc':LIVE_ZC},'reference_constants':C,'methodology_warning':'Pre-31-Mar-2021 NIFTY P/E history used the older standalone-earnings methodology; current methodology uses consolidated trailing earnings where available. Pre-2021 rows are therefore a mechanical sensitivity series, not directly comparable to current V3.6 valuation levels.','repo_nomenclature_warning':'Before 29-Oct-2004 RBI repo/reverse-repo nomenclature was opposite to current international usage; historical policy-rate values use the current-comparable RBI/Reuters convention.','rows_data':public.to_dict(orient='records')}
    JSON_OUT.write_text(json.dumps(meta,indent=2,allow_nan=False),encoding='utf-8');return meta

if __name__=='__main__':
    try:
        x=build();print(json.dumps({'status':x['status'],'rows':x['rows'],'start':x['start'],'end':x['end'],'missing_months':x['missing_months']}))
    except Exception as e:
        error={'status':'unavailable','error':f'{type(e).__name__}: {e}'};JSON_OUT.write_text(json.dumps(error,indent=2),encoding='utf-8');print(json.dumps(error));raise
