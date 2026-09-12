#!/usr/bin/env python3
"""Research the Jan-2000 allocation strategy with investable mutual-fund NAVs.
Research only: never changes the live V3.6 allocation model.
"""
from __future__ import annotations
from datetime import date
from pathlib import Path
from difflib import SequenceMatcher
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, as_completed
import json, math, re, time
import numpy as np
import pandas as pd
import requests
import update_data as b

ROOT=Path(__file__).resolve().parents[1]
ALLOC=ROOT/'data'/'backtest_monthly_2000.csv'
OUT=ROOT/'data'/'fund_strategy_rank.json'
START=pd.Timestamp('2000-01-01'); TODAY=pd.Timestamp(date.today())
MFAPI='https://api.mfapi.in'; HEAD={'User-Agent':'Mozilla/5.0 AnupNiftyValuationResearch/1.1'}
EQUITY_CODE=101349
DEBT_CODE=101758
CANDIDATES=[
 'HDFC Flexi Cap Fund','HDFC Large Cap Fund','HDFC ELSS Tax saver',
 'Franklin India Flexi Cap Fund','Franklin India Bluechip Fund','Franklin India Prima Fund',
 'Nippon India Growth Fund','Nippon India Vision Fund','SBI Contra Fund','SBI Long Term Equity Fund',
 'Tata Mid Cap Growth Fund','Tata Large & Mid Cap Fund','Tata ELSS Tax Saver Fund',
 'Canara Robeco ELSS Tax Saver','Aditya Birla Sun Life Tax Relief 96','DSP Flexi Cap Fund',
 'Kotak Bluechip Fund','ICICI Prudential Multicap Fund','UTI Mastershare Unit Scheme',
 'LIC MF Large & Mid Cap Fund','JM Flexicap Fund','Sundaram Diversified Equity','Taurus Starshare','HSBC Value Fund']

def get(url,params=None,timeout=45,retries=3,want_json=False):
    err=None
    for i in range(retries):
        try:
            r=requests.get(url,params=params,headers=HEAD,timeout=timeout);r.raise_for_status()
            return r.json() if want_json else r.text
        except Exception as e:
            err=e; time.sleep(1.25*(i+1))
    raise RuntimeError(f'GET failed {url}: {err}')

def mf_history(code):
    j=get(f'{MFAPI}/mf/{int(code)}',want_json=True)
    pts=[]
    for x in j.get('data') or []:
        dt=pd.to_datetime(x.get('date'),dayfirst=True,errors='coerce'); nav=pd.to_numeric(x.get('nav'),errors='coerce')
        if pd.notna(dt) and pd.notna(nav) and float(nav)>0: pts.append((dt.normalize(),float(nav)))
    if not pts: raise RuntimeError(f'No NAV history for {code}')
    s=pd.DataFrame(pts,columns=['date','nav']).drop_duplicates('date').set_index('date').nav.sort_index()
    return s,j.get('meta') or {}

def first_monthly(s): return s.sort_index().groupby(s.index.to_period('M')).first()
def latest(s): return (float(s.iloc[-1]),s.index[-1]) if len(s) else (None,None)
def first_near(s,dt,max_days=20):
    q=s[(s.index>=dt)&(s.index<=dt+pd.Timedelta(days=max_days))]
    return (float(q.iloc[0]),q.index[0]) if len(q) else (None,None)

def nifty_tri_daily():
    from jugaad_data.nse import index_tri_raw
    rows=index_tri_raw('NIFTY 50','NIFTY 50',date(2000,1,1),date.today()); pts=[]
    for x in rows or []:
        dt=b.pdate(b.pick(x,['Date','DATE','HistoricalDate','Index Date']))
        val=b.fnum(b.pick(x,['Total Returns Index','TRI','Close','CLOSE','Closing Index Value','Index Value']))
        if dt and val and val>0: pts.append((pd.Timestamp(dt),float(val)))
    if len(pts)<1000: raise RuntimeError(f'Insufficient NIFTY TRI history: {len(pts)}')
    return pd.DataFrame(pts,columns=['date','value']).drop_duplicates('date').set_index('date').value.sort_index()

def short_rate_monthly():
    # Prior-month India short-term interest rate. Direct requests are used rather
    # than the dashboard HTTP wrapper because FRED occasionally stalls on runners.
    url='https://fred.stlouisfed.org/graph/fredgraph.csv?id=INDLOCOSTORSTM'
    text=get(url,timeout=60,retries=4)
    q=pd.read_csv(StringIO(text)); q.columns=['date','value'];q['date']=pd.to_datetime(q.date,errors='coerce');q['value']=pd.to_numeric(q.value,errors='coerce')
    q=q.dropna().sort_values('date'); q['month']=q.date.dt.to_period('M')
    s=q.groupby('month').value.last().astype(float).sort_index()
    if pd.Period('1999-12','M') not in s.index: raise RuntimeError('Short-rate proxy lacks Dec-1999')
    return s

def rate_return(rate,days=None):
    return (1+float(rate)/100)**((days/365.2425) if days is not None else 1/12)-1

def sleeve_return(month,series_m,series_daily,proxy=None):
    nm=month+1
    if month in series_m.index:
        a=float(series_m.loc[month])
        if nm in series_m.index: return float(series_m.loc[nm])/a-1
        v,_=latest(series_daily); return v/a-1 if v else None
    return proxy(month) if proxy else None

def build_strategy():
    alloc=pd.read_csv(ALLOC);alloc['month']=pd.to_datetime(alloc.Date).dt.to_period('M');alloc=alloc.set_index('month')
    eq_nav,eq_meta=mf_history(EQUITY_CODE);db_nav,db_meta=mf_history(DEBT_CODE);tri=nifty_tri_daily();rates=short_rate_monthly()
    eq_m,db_m,tri_m=first_monthly(eq_nav),first_monthly(db_nav),first_monthly(tri)
    months=pd.period_range('2000-01',pd.Period(date.today(),freq='M'),freq='M')
    wealth=1e7; timeline=[]; counts={'equity_fund':0,'equity_tri_proxy':0,'debt_fund':0,'debt_rate_proxy':0}
    for mo in months:
        if mo not in alloc.index: continue
        w=float(alloc.loc[mo,'Equity %'])/100
        if mo in eq_m.index:
            er=sleeve_return(mo,eq_m,eq_nav); counts['equity_fund']+=1; es='ICICI Pru Nifty 50 Index Fund Regular Growth'
        else:
            er=sleeve_return(mo,tri_m,tri); counts['equity_tri_proxy']+=1; es='NIFTY 50 TRI proxy'
        if mo in db_m.index:
            dr=sleeve_return(mo,db_m,db_nav); counts['debt_fund']+=1; ds='ICICI Pru Short Term Fund Regular Growth'
        else:
            rate=rates.get(mo-1,np.nan)
            if not pd.notna(rate): continue
            days=(date.today()-mo.start_time.date()).days if mo==months[-1] else None
            dr=rate_return(rate,max(0,days) if days is not None else None); counts['debt_rate_proxy']+=1; ds='India short-term-rate proxy (prior month)'
        if er is None or dr is None or not all(math.isfinite(float(x)) for x in (er,dr)): continue
        start=wealth; wealth=start*(w*(1+er)+(1-w)*(1+dr))
        timeline.append({'month':str(mo),'equity_weight_pct':100*w,'equity_return_pct':100*er,'debt_return_pct':100*dr,'equity_source':es,'debt_source':ds,'end_value':wealth})
    end=max(eq_nav.index.max(),db_nav.index.max(),tri.index.max()); years=(end-START).days/365.2425
    common=sorted(set(eq_m.index)&set(db_m.index)&set(alloc.index)); strict=None
    if common:
        sm=common[0];v=1e7;used=0
        for mo in months[months.get_loc(sm):]:
            if mo not in alloc.index or mo not in eq_m.index or mo not in db_m.index: continue
            er=sleeve_return(mo,eq_m,eq_nav);dr=sleeve_return(mo,db_m,db_nav)
            if er is None or dr is None: continue
            w=float(alloc.loc[mo,'Equity %'])/100;v*=w*(1+er)+(1-w)*(1+dr);used+=1
        yrs=(max(eq_nav.index.max(),db_nav.index.max())-sm.start_time).days/365.2425
        strict={'start_month':str(sm),'months':used,'ending_value_inr':v,'multiple_x':v/1e7,'cagr_pct':100*((v/1e7)**(1/yrs)-1)}
    return {'start_value_inr':1e7,'start_date':'2000-01-01','end_date':str(end.date()),'ending_value_inr':wealth,'multiple_x':wealth/1e7,'cagr_pct':100*((wealth/1e7)**(1/years)-1),'months_used':len(timeline),'source_month_counts':counts,
      'equity_fund':{'scheme_code':EQUITY_CODE,'name':eq_meta.get('scheme_name'),'nav_first_date':str(eq_nav.index.min().date()),'nav_last_date':str(eq_nav.index.max().date())},
      'debt_fund':{'scheme_code':DEBT_CODE,'name':db_meta.get('scheme_name'),'nav_first_date':str(db_nav.index.min().date()),'nav_last_date':str(db_nav.index.max().date())},'strict_actual_funds':strict,'timeline':timeline}

def norm(s): return re.sub(r'[^a-z0-9]+',' ',str(s).lower()).strip()
def choose(query,results):
    bad=('direct','idcw','dividend','bonus','segregated','institutional','weekly','monthly','quarterly','payout','reinvestment')
    c=[]
    for x in results or []:
        name=x.get('schemeName') or ''; n=norm(name)
        if any(z in n for z in bad) or ('growth' not in n and 'cumulative' not in n): continue
        c.append((SequenceMatcher(None,norm(query),n).ratio()+(.08 if 'regular' in n else 0),x))
    return max(c,key=lambda z:z[0])[1] if c else None

def one_candidate(query):
    try:
        hit=choose(query,get(f'{MFAPI}/mf/search',params={'q':query},timeout=25,retries=2,want_json=True))
        if not hit:return None,{'query':query,'error':'no regular-growth match'}
        code=hit.get('schemeCode');s,meta=mf_history(code);sv,sdt=first_near(s,START,20);ev,edt=latest(s)
        if sv is None or sdt>pd.Timestamp('2000-01-20'):return None,{'query':query,'selected':hit.get('schemeName'),'error':'no NAV close enough to Jan-2000'}
        yrs=(edt-sdt).days/365.2425;mult=ev/sv
        return {'name':meta.get('scheme_name') or hit.get('schemeName'),'scheme_code':int(code),'start_date':str(sdt.date()),'end_date':str(edt.date()),'cagr_pct':100*(mult**(1/yrs)-1),'value_of_1cr_inr':1e7*mult,'multiple_x':mult},None
    except Exception as e:return None,{'query':query,'error':f'{type(e).__name__}: {e}'}

def rank(strategy):
    rows=[];errors=[]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures=[pool.submit(one_candidate,q) for q in CANDIDATES]
        for f in as_completed(futures):
            r,e=f.result(); rows.extend([r] if r else []); errors.extend([e] if e else [])
    rows.append({'name':'Anup monthly allocation methodology (reconstructed)','scheme_code':None,'start_date':strategy['start_date'],'end_date':strategy['end_date'],'cagr_pct':strategy['cagr_pct'],'value_of_1cr_inr':strategy['ending_value_inr'],'multiple_x':strategy['multiple_x'],'is_methodology':True})
    rows=sorted(rows,key=lambda x:x['cagr_pct'],reverse=True)
    for i,x in enumerate(rows,1):x['rank']=i
    mr=next(x['rank'] for x in rows if x.get('is_methodology'))
    return {'cohort_size_including_methodology':len(rows),'methodology_rank':mr,'rows':rows,'errors':errors,'warning':'Screened surviving-fund cohort, not a complete Jan-2000 universe; survivorship and selection bias apply.'}

def main():
    s=build_strategy();r=rank(s)
    out={'status':'complete','generated_on':str(date.today()),'basis':{'rebalancing':'monthly using backtest_monthly_2000.csv','taxes_loads_slippage':'excluded','fund_plan':'regular growth','pre_inception_equity':'NIFTY 50 TRI proxy','pre_inception_debt':'prior-month India short-term-rate proxy','ranking_scope':'screened major surviving regular-growth equity funds with NAV near Jan-2000'},'strategy':s,'ranking':r}
    OUT.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'status':'complete','ending_cr':s['ending_value_inr']/1e7,'cagr_pct':s['cagr_pct'],'rank':r['methodology_rank'],'cohort':r['cohort_size_including_methodology'],'eq_nav_first':s['equity_fund']['nav_first_date'],'debt_nav_first':s['debt_fund']['nav_first_date']}))
if __name__=='__main__':main()
