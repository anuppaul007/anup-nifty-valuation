#!/usr/bin/env python3
"""Research the Jan-2000 monthly allocation table with investable fund returns.

Outputs data/fund_strategy_rank.json. This is research only; it does not alter
live V3.6 parameters or the website allocation.

Important implementation choices
--------------------------------
* ICICI Prudential Short Term Fund launched in Oct-2001 and ICICI Prudential
  Nifty 50 Index Fund launched in Feb-2002, so an exact all-ICICI fund strategy
  cannot exist from 1-Jan-2000.
* The continuous Jan-2000 reconstruction therefore uses NIFTY 50 TRI for the
  equity sleeve before usable ICICI index-fund NAV history and an India
  short-term interest-rate cash proxy before usable ICICI short-term-fund NAV
  history. Once usable fund NAV histories are present, actual regular-growth NAV
  returns are used.
* Monthly target weights are those in data/backtest_monthly_2000.csv. The target
  is rebalanced at the first available observation in each month. No taxes,
  loads, brokerage, or slippage are charged.
* The survivor ranking is a screened cohort of major active regular-growth
  equity funds known to have long histories. It is not a complete census and is
  explicitly subject to survivorship bias.
"""
from __future__ import annotations
from datetime import date, timedelta
from pathlib import Path
from difflib import SequenceMatcher
import json, math, re, time
import numpy as np
import pandas as pd
import requests
import update_data as b

ROOT=Path(__file__).resolve().parents[1]
ALLOC=ROOT/'data'/'backtest_monthly_2000.csv'
OUT=ROOT/'data'/'fund_strategy_rank.json'
START=pd.Timestamp('2000-01-01')
TODAY=pd.Timestamp(date.today())
MFAPI='https://api.mfapi.in'
HEAD={'User-Agent':'AnupNiftyValuationResearch/1.0'}
EQUITY_CODE=101349  # ICICI Prudential Nifty 50 Index Fund - regular growth/cumulative
DEBT_CODE=101758    # ICICI Prudential Short Term Fund - regular growth

CANDIDATES=[
 'HDFC Flexi Cap Fund','HDFC Large Cap Fund','HDFC ELSS Tax saver',
 'Franklin India Flexi Cap Fund','Franklin India Bluechip Fund','Franklin India Prima Fund',
 'Nippon India Growth Fund','Nippon India Vision Fund',
 'SBI Contra Fund','SBI Long Term Equity Fund',
 'Tata Mid Cap Growth Fund','Tata Large & Mid Cap Fund','Tata ELSS Tax Saver Fund',
 'Canara Robeco ELSS Tax Saver','Aditya Birla Sun Life Tax Relief 96',
 'DSP Flexi Cap Fund','Kotak Bluechip Fund','ICICI Prudential Multicap Fund',
 'UTI Mastershare Unit Scheme','LIC MF Large & Mid Cap Fund','JM Flexicap Fund',
 'Sundaram Diversified Equity','Taurus Starshare','HSBC Value Fund'
]


def get_json(url,params=None,timeout=40,retries=3):
    last=None
    for i in range(retries):
        try:
            r=requests.get(url,params=params,headers=HEAD,timeout=timeout);r.raise_for_status();return r.json()
        except Exception as e:
            last=e;time.sleep(1.5*(i+1))
    raise RuntimeError(f'GET failed {url}: {last}')

def mf_history(code):
    j=get_json(f'{MFAPI}/mf/{int(code)}')
    data=j.get('data') or []
    pts=[]
    for x in data:
        dt=pd.to_datetime(x.get('date'),dayfirst=True,errors='coerce');nav=pd.to_numeric(x.get('nav'),errors='coerce')
        if pd.notna(dt) and pd.notna(nav) and float(nav)>0:pts.append((dt.normalize(),float(nav)))
    if not pts:raise RuntimeError(f'No NAV history for scheme {code}')
    s=pd.DataFrame(pts,columns=['date','nav']).drop_duplicates('date').set_index('date').nav.sort_index()
    return s,j.get('meta') or {}

def first_monthly(s):
    s=s.sort_index();return s.groupby(s.index.to_period('M')).first()

def latest_on_or_before(s,dt):
    q=s[s.index<=pd.Timestamp(dt)]
    return (float(q.iloc[-1]),q.index[-1]) if len(q) else (None,None)

def first_on_or_after(s,dt,max_days=15):
    dt=pd.Timestamp(dt);q=s[(s.index>=dt)&(s.index<=dt+pd.Timedelta(days=max_days))]
    return (float(q.iloc[0]),q.index[0]) if len(q) else (None,None)

def nifty_tri_daily():
    from jugaad_data.nse import index_tri_raw
    rows=index_tri_raw('NIFTY 50','NIFTY 50',date(2000,1,1),date.today())
    pts=[]
    for x in rows or []:
        dt=b.pdate(b.pick(x,['Date','DATE','HistoricalDate','Index Date']))
        val=b.fnum(b.pick(x,['Total Returns Index','TRI','Close','CLOSE','Closing Index Value','Index Value']))
        if dt and val and val>0:pts.append((pd.Timestamp(dt),float(val)))
    if len(pts)<1000:raise RuntimeError(f'Insufficient NIFTY 50 TRI history: {len(pts)}')
    return pd.DataFrame(pts,columns=['date','value']).drop_duplicates('date').set_index('date').value.sort_index()

def short_rate_monthly():
    # OECD leading-indicator component provides a monthly India short-term rate
    # from Apr-1999. Use the prior month to avoid same-month look-ahead.
    q=b.fred('INDLOCOSTORSTM')
    q['date']=pd.to_datetime(q.date);q['value']=pd.to_numeric(q.value,errors='coerce')
    s=q.dropna().set_index(q.dropna().date.dt.to_period('M')).value.astype(float).sort_index()
    return s

def proxy_return_from_rate(rate_pct,days=None):
    # Effective monthly or day-count return from an annual rate.
    if days is None:return (1+float(rate_pct)/100)**(1/12)-1
    return (1+float(rate_pct)/100)**(float(days)/365.2425)-1

def build_strategy():
    alloc=pd.read_csv(ALLOC);alloc['month']=pd.to_datetime(alloc['Date']).dt.to_period('M');alloc=alloc.set_index('month')
    eq_nav,eq_meta=mf_history(EQUITY_CODE);db_nav,db_meta=mf_history(DEBT_CODE)
    tri=nifty_tri_daily();tri_m=first_monthly(tri);eq_m=first_monthly(eq_nav);db_m=first_monthly(db_nav);rates=short_rate_monthly()
    months=pd.period_range('2000-01',pd.Period(date.today(),freq='M'),freq='M')
    wealth=10_000_000.0;timeline=[];source_counts={'equity_fund':0,'equity_proxy':0,'debt_fund':0,'debt_proxy':0}
    last_complete=None
    for i,mo in enumerate(months):
        if mo not in alloc.index:continue
        w=float(alloc.loc[mo,'Equity %'])/100.0
        next_m=mo+1
        # Find sleeve returns. For historical full months use first observation
        # this month to first observation next month; for current partial month
        # use first observation this month to latest available observation.
        eq_source='ICICI Pru Nifty 50 Index Fund Regular Growth' if mo in eq_m.index else 'NIFTY 50 TRI proxy'
        db_source='ICICI Pru Short Term Fund Regular Growth' if mo in db_m.index else 'India short-term-rate proxy'
        if mo in eq_m.index:
            a=float(eq_m.loc[mo]);
            if next_m in eq_m.index:bval=float(eq_m.loc[next_m]);er=bval/a-1
            else:
                last,lastdt=latest_on_or_before(eq_nav,TODAY);er=(last/a-1) if last else None
            source_counts['equity_fund']+=1
        else:
            if mo not in tri_m.index:continue
            a=float(tri_m.loc[mo])
            if next_m in tri_m.index:er=float(tri_m.loc[next_m])/a-1
            else:
                last,lastdt=latest_on_or_before(tri,TODAY);er=(last/a-1) if last else None
            source_counts['equity_proxy']+=1
        if mo in db_m.index:
            a=float(db_m.loc[mo])
            if next_m in db_m.index:dr=float(db_m.loc[next_m])/a-1
            else:
                last,lastdt=latest_on_or_before(db_nav,TODAY);dr=(last/a-1) if last else None
            source_counts['debt_fund']+=1
        else:
            prior=mo-1;rate=rates.get(prior,np.nan)
            if not math.isfinite(float(rate)) if pd.notna(rate) else True:continue
            if mo==months[-1]:
                days=max(0,(date.today()-mo.start_time.date()).days);dr=proxy_return_from_rate(rate,days)
            else:dr=proxy_return_from_rate(rate)
            source_counts['debt_proxy']+=1
        if er is None or dr is None or not all(math.isfinite(float(x)) for x in (er,dr)):continue
        start_wealth=wealth;wealth=start_wealth*(w*(1+er)+(1-w)*(1+dr))
        timeline.append({'month':str(mo),'equity_weight_pct':100*w,'equity_return_pct':100*er,'debt_return_pct':100*dr,
                         'equity_source':eq_source,'debt_source':db_source,'start_value':start_wealth,'end_value':wealth})
        last_complete=mo
    if not timeline:raise RuntimeError('Strategy produced no months')
    end_date=max(eq_nav.index.max(),db_nav.index.max(),tri.index.max())
    years=(end_date-START).days/365.2425;cagr=(wealth/10_000_000)**(1/years)-1
    # Strict actual-fund period: first calendar month in which both regular-growth
    # NAV series have a first-of-month observation.
    common=sorted(set(eq_m.index)&set(db_m.index)&set(alloc.index))
    strict=None
    if common:
        start_m=common[0];v=10_000_000.0;used=0
        for mo in months[months.get_loc(start_m):]:
            if mo not in alloc.index or mo not in eq_m.index or mo not in db_m.index:continue
            w=float(alloc.loc[mo,'Equity %'])/100;nm=mo+1
            if nm in eq_m.index:er=float(eq_m.loc[nm])/float(eq_m.loc[mo])-1
            else:
                last,_=latest_on_or_before(eq_nav,TODAY);er=last/float(eq_m.loc[mo])-1 if last else None
            if nm in db_m.index:dr=float(db_m.loc[nm])/float(db_m.loc[mo])-1
            else:
                last,_=latest_on_or_before(db_nav,TODAY);dr=last/float(db_m.loc[mo])-1 if last else None
            if er is None or dr is None:continue
            v=v*(w*(1+er)+(1-w)*(1+dr));used+=1
        sdt=start_m.start_time;ey=max(eq_nav.index.max(),db_nav.index.max());yrs=(ey-sdt).days/365.2425
        strict={'start_month':str(start_m),'months':used,'ending_value_inr':v,'multiple_x':v/10_000_000,'cagr_pct':100*((v/10_000_000)**(1/yrs)-1) if yrs>0 else None,
                'note':'₹1 crore is reset at the first common month with actual NAV history for both requested regular-growth funds.'}
    return {
      'start_value_inr':10_000_000,'start_date':'2000-01-01','end_date':str(end_date.date()),'ending_value_inr':wealth,
      'multiple_x':wealth/10_000_000,'cagr_pct':100*cagr,'months_used':len(timeline),'last_month':str(last_complete),
      'source_month_counts':source_counts,
      'equity_fund':{'scheme_code':EQUITY_CODE,'name':eq_meta.get('scheme_name'),'nav_first_date':str(eq_nav.index.min().date()),'nav_last_date':str(eq_nav.index.max().date())},
      'debt_fund':{'scheme_code':DEBT_CODE,'name':db_meta.get('scheme_name'),'nav_first_date':str(db_nav.index.min().date()),'nav_last_date':str(db_nav.index.max().date())},
      'strict_actual_funds':strict,'timeline':timeline
    }

def normalize_name(s):return re.sub(r'[^a-z0-9]+',' ',str(s).lower()).strip()
def pick_search_result(query,results):
    bad=('direct','idcw','dividend','bonus','segregated','institutional','weekly','monthly','quarterly','payout','reinvestment')
    qn=normalize_name(query);cands=[]
    for x in results or []:
        name=x.get('schemeName') or x.get('scheme_name') or ''
        n=normalize_name(name)
        if any(b in n for b in bad):continue
        if 'growth' not in n and 'cumulative' not in n:continue
        sim=SequenceMatcher(None,qn,n).ratio();bonus=.08 if 'regular' in n else 0
        cands.append((sim+bonus,x))
    return max(cands,key=lambda z:z[0])[1] if cands else None

def rank_candidates(strategy):
    rows=[];errors=[]
    for query in CANDIDATES:
        try:
            results=get_json(f'{MFAPI}/mf/search',{'q':query},timeout=30)
            hit=pick_search_result(query,results)
            if not hit:errors.append({'query':query,'error':'no regular-growth search match'});continue
            code=hit.get('schemeCode') or hit.get('scheme_code');s,meta=mf_history(code)
            sv,sdt=first_on_or_after(s,START,20);ev,edt=latest_on_or_before(s,TODAY)
            if sv is None or ev is None or sdt>pd.Timestamp('2000-01-20'):
                errors.append({'query':query,'selected':hit.get('schemeName'),'scheme_code':code,'error':'no NAV close enough to Jan-2000'});continue
            yrs=(edt-sdt).days/365.2425;cagr=(ev/sv)**(1/yrs)-1
            rows.append({'name':meta.get('scheme_name') or hit.get('schemeName'),'scheme_code':int(code),'start_date':str(sdt.date()),'end_date':str(edt.date()),
                         'start_nav':sv,'end_nav':ev,'cagr_pct':100*cagr,'value_of_1cr_inr':10_000_000*(ev/sv),'multiple_x':ev/sv})
        except Exception as e:errors.append({'query':query,'error':f'{type(e).__name__}: {e}'})
    rows.append({'name':'Anup monthly allocation methodology (reconstructed)','scheme_code':None,'start_date':strategy['start_date'],'end_date':strategy['end_date'],
                 'cagr_pct':strategy['cagr_pct'],'value_of_1cr_inr':strategy['ending_value_inr'],'multiple_x':strategy['multiple_x'],'is_methodology':True})
    rows=sorted(rows,key=lambda x:x['cagr_pct'],reverse=True)
    for i,x in enumerate(rows,1):x['rank']=i
    method=next(x for x in rows if x.get('is_methodology'))
    return {'cohort_size_including_methodology':len(rows),'methodology_rank':method['rank'],'rows':rows,'errors':errors,
            'warning':'Screened surviving-fund cohort, not the complete Jan-2000 mutual-fund universe. Ranking has survivorship and selection bias.'}

def main():
    strategy=build_strategy();ranking=rank_candidates(strategy)
    out={'status':'complete','generated_on':str(date.today()),'basis':{
      'rebalancing':'monthly at first available observation using Date/Equity%/Debt% from backtest_monthly_2000.csv',
      'taxes_loads_slippage':'excluded','fund_plan':'regular growth, because direct plans did not exist in 2000',
      'pre_inception_equity':'NIFTY 50 TRI proxy','pre_inception_debt':'prior-month India short-term interest rate cash proxy',
      'ranking_scope':'screened major surviving regular-growth equity funds with NAV near Jan-2000'},
      'strategy':strategy,'ranking':ranking}
    OUT.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'status':'complete','ending_cr':strategy['ending_value_inr']/1e7,'cagr_pct':strategy['cagr_pct'],'rank':ranking['methodology_rank'],'cohort':ranking['cohort_size_including_methodology'],
                      'eq_nav_first':strategy['equity_fund']['nav_first_date'],'debt_nav_first':strategy['debt_fund']['nav_first_date']}))
if __name__=='__main__':main()
