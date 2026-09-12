#!/usr/bin/env python3
"""Long-history multi-asset research backtest, Jan-2000 onward.

Purpose
-------
Test whether the new Gold/Silver diversification layer improves the existing
monthly NIFTY/debt allocation reconstruction. Bitcoin is evaluated only in a
separate *funded tactical* research variant; it does not change the live
retirement-core policy, where BTC remains outside the 100% core allocation.

Important limitations
---------------------
* The base NIFTY signal is the existing common-history valuation reconstruction
  in data/backtest_monthly_2000.csv, not the full modern V3.6 macro model.
* Gold/Silver weights reproduce the current research-v1 formulas as closely as
  historical data permit. Gold requires US real yield, broad USD, VIX and gold
  momentum. Silver uses the NBS China manufacturing PMI, gold/silver ratio and
  silver momentum. Metals remain at 0 until BOTH models are eligible.
* Historical macro observations are latest-revised series, not vintage release
  databases. No future prices are used, but this is not a perfect real-time
  release-vintage simulation.
* Metal and BTC returns are synthetic INR returns: USD market price multiplied
  by USD/INR. This is more relevant to an Indian investor than USD-only returns,
  but it is not an ETF total-return series and ignores product tracking error.
* Taxes, exit loads and product expense ratios are excluded. A separate 10-bps
  one-way turnover sensitivity is reported.
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from pathlib import Path
import json, math, time
import numpy as np
import pandas as pd
import requests
import update_data as b
import fund_strategy_rank as fs

ROOT=Path(__file__).resolve().parents[1]
ALLOC=ROOT/'data'/'backtest_monthly_2000.csv'
OUT=ROOT/'data'/'multiasset_backtest.json'
START=pd.Timestamp('2000-01-01')
HEAD={'User-Agent':'Mozilla/5.0 AnupNiftyValuationResearch/1.0'}


def finite(x):
    try:return x is not None and math.isfinite(float(x))
    except (TypeError,ValueError):return False

def clip(x,a,b):return max(a,min(b,float(x)))
def squash(x,scale=1.5):return float(np.tanh(float(x)/float(scale)))

def yahoo_history(symbol,start='1999-01-01'):
    p1=int(pd.Timestamp(start,tz='UTC').timestamp());p2=int(pd.Timestamp.now(tz='UTC').timestamp())+86400
    url=f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
    r=requests.get(url,params={'period1':p1,'period2':p2,'interval':'1d','events':'history','includeAdjustedClose':'true'},headers=HEAD,timeout=35);r.raise_for_status()
    j=r.json()['chart']['result'][0];pts=[]
    for ts,v in zip(j.get('timestamp') or [],((j.get('indicators') or {}).get('quote') or [{}])[0].get('close') or []):
        if finite(v) and float(v)>0:pts.append((pd.to_datetime(ts,unit='s').normalize(),float(v)))
    if len(pts)<250:raise RuntimeError(f'{symbol}: insufficient Yahoo history {len(pts)}')
    return pd.DataFrame(pts,columns=['date','value']).drop_duplicates('date').set_index('date').value.sort_index()

def fred(series):
    url='https://fred.stlouisfed.org/graph/fredgraph.csv'
    r=requests.get(url,params={'id':series},headers=HEAD,timeout=35);r.raise_for_status()
    t=pd.read_csv(pd.io.common.StringIO(r.text));dc=t.columns[0];vc=t.columns[-1]
    q=pd.DataFrame({'date':pd.to_datetime(t[dc],errors='coerce'),'value':pd.to_numeric(t[vc],errors='coerce')}).dropna()
    s=q.drop_duplicates('date').set_index('date').value.astype(float).sort_index()
    if s.empty:raise RuntimeError(f'FRED {series}: no observations')
    return s

def china_pmi():
    url='https://chinadata.live/api/v2/data/china-pmi'
    r=requests.get(url,headers=HEAD,timeout=30);r.raise_for_status();j=r.json()
    rows=(((j or {}).get('data') or {}).get('data') or [])
    pts=[]
    for x in rows:
        try:pts.append((pd.Period(str(x['date']),freq='M'),float(x['value'])))
        except Exception:pass
    if len(pts)<120:raise RuntimeError('China PMI historical series unavailable')
    return pd.Series(dict(pts),dtype=float).sort_index()

def first_monthly(s):
    q=s.sort_index();return q.groupby(q.index.to_period('M')).first()
def last_on_or_before(s,dt,max_days=None):
    q=s[s.index<=pd.Timestamp(dt)]
    if max_days is not None:q=q[q.index>=pd.Timestamp(dt)-pd.Timedelta(days=max_days)]
    return (float(q.iloc[-1]),q.index[-1]) if len(q) else (None,None)
def first_on_or_after(s,dt,max_days=12):
    q=s[(s.index>=pd.Timestamp(dt))&(s.index<=pd.Timestamp(dt)+pd.Timedelta(days=max_days))]
    return (float(q.iloc[0]),q.index[0]) if len(q) else (None,None)
def pct_near_year(s,dt):
    now,_=last_on_or_before(s,dt,10)
    old,_=last_on_or_before(s,pd.Timestamp(dt)-pd.DateOffset(years=1),25)
    return 100*(now/old-1) if finite(now) and finite(old) and old>0 else None

def rolling_price_features(s,dt):
    q=s[s.index<=pd.Timestamp(dt)]
    if len(q)<260:return None
    px=float(q.iloc[-1]);ma200=float(q.iloc[-200:].mean());mom=pct_near_year(q,q.index[-1])
    window=q[q.index>=q.index[-1]-pd.DateOffset(years=3)]
    if not finite(mom) or len(window)<250:return None
    hi=float(window.max())
    return {'price':px,'vs_ma200_pct':100*(px/ma200-1),'momentum_12m_pct':mom,'drawdown_3y_pct':100*(px/hi-1)}

def zhist(current,hist,n,floor=1e-9,max_obs=None):
    h=pd.Series(hist,dtype=float).replace([np.inf,-np.inf],np.nan).dropna()
    if max_obs:h=h.tail(int(max_obs))
    if len(h)<n:return None
    sd=float(h.std(ddof=0))
    if not finite(sd) or sd<floor:return None
    return clip((float(current)-float(h.mean()))/sd,-3,3)

def build_macro():
    real=fred('DFII10');usd=fred('DTWEXBGS');vix=fred('VIXCLS');fed=fred('WALCL');fx=fred('DEXINUS')
    usd_m=usd.groupby(usd.index.to_period('M')).mean();usd3=100*(usd_m/usd_m.shift(3)-1)
    fed6=100*(fed/fed.shift(26)-1)
    return {'real':real,'usd':usd,'usd_m':usd_m,'usd3':usd3,'vix':vix,'fed':fed,'fed6':fed6,'fx':fx,'china':china_pmi()}

def gold_target(gold_usd,mac,dt):
    real,_=last_on_or_before(mac['real'],dt,10);vix,_=last_on_or_before(mac['vix'],dt,10)
    mo=pd.Period(pd.Timestamp(dt),freq='M')-1
    if mo not in mac['usd3'].index:return None
    usd3=float(mac['usd3'].loc[mo]);mom=pct_near_year(gold_usd,dt)
    if not all(finite(x) for x in (real,vix,usd3,mom)):return None
    rs=squash(-(real-1.5),1.25);us=squash(-usd3,4.0);ts=squash(mom,20.0);vs=squash(vix-20,10.0)
    score=.35*rs+.25*us+.25*ts+.15*vs
    return {'score':score,'target':clip(13+5*score,8,18)}

def silver_target(gold_usd,silver_usd,mac,dt):
    dt=pd.Timestamp(dt);g=gold_usd[gold_usd.index<=dt];s=silver_usd[silver_usd.index<=dt]
    x=pd.concat([g.rename('g'),s.rename('s')],axis=1).dropna();x=x[(x.g>0)&(x.s>0)]
    feat=rolling_price_features(silver_usd,dt)
    pmi_m=pd.Period(dt,freq='M')-1
    if len(x)<260 or feat is None or pmi_m not in mac['china'].index:return None
    ratio=x.g/x.s;cur=float(ratio.iloc[-1]);hist=ratio.iloc[:-1].tail(756)
    z=zhist(cur,hist,250,1e-9,756)
    if not finite(z):return None
    rel=squash(z,1.5);pmi=float(mac['china'].loc[pmi_m]);industrial=squash((pmi-50)/1.75,1.5);trend=squash(feat['momentum_12m_pct'],30.0)
    score=.45*rel+.30*industrial+.25*trend
    return {'score':score,'target':clip(3.5+3.5*score,0,7),'pmi':pmi}

def global_liquidity(mac,dt):
    dt=pd.Timestamp(dt)
    real_q=mac['real'][mac['real'].index<=dt];vix_q=mac['vix'][mac['vix'].index<=dt];fed6_q=mac['fed6'][mac['fed6'].index<=dt]
    if not len(real_q) or not len(vix_q) or not len(fed6_q):return None
    rv=float(real_q.iloc[-1]);vv=float(vix_q.iloc[-1]);fv=float(fed6_q.iloc[-1])
    rz=zhist(rv,real_q.iloc[:-1],60,.15,756);vz=zhist(vv,vix_q.iloc[:-1],60,1,756);fz=zhist(fv,fed6_q.iloc[:-1],40,.4,156)
    mo=pd.Period(dt,freq='M')-1
    if mo not in mac['usd3'].index:return None
    uv=float(mac['usd3'].loc[mo]);uz=zhist(uv,mac['usd3'].loc[:mo].iloc[:-1],36,.4,120)
    if not all(finite(x) for x in (rz,vz,fz,uz)):return None
    scores=[squash(-rz),squash(fz),squash(-uz),squash(-vz)]
    return .40*scores[0]+.25*scores[1]+.20*scores[2]+.15*scores[3]

def btc_target(btc_usd,mac,dt):
    feat=rolling_price_features(btc_usd,dt);liq=global_liquidity(mac,dt)
    if feat is None or not finite(liq):return None
    trend=squash(feat['vs_ma200_pct'],20.0);mom=squash(feat['momentum_12m_pct'],60.0);value=squash((-feat['drawdown_3y_pct'])-25,20.0)
    score=.30*trend+.20*mom+.25*float(liq)+.25*value
    if score<-.50:t=0.0
    elif score<-.15:t=2.5
    elif score<.25:t=5.0
    elif score<.55:t=7.5
    else:t=10.0
    return {'score':score,'target':t}

def inr_series(usd,fx):
    # Align each USD market close with latest available USD/INR observation.
    left=usd.rename('usd').reset_index().rename(columns={'index':'date'}).sort_values('date')
    right=fx.rename('fx').reset_index().rename(columns={'index':'date'}).sort_values('date')
    z=pd.merge_asof(left,right,on='date',direction='backward',tolerance=pd.Timedelta(days=7)).dropna()
    s=(z.usd*z.fx);s.index=z.date
    return s.sort_index()

def monthly_return(s,mo,last_partial=True):
    start,_=first_on_or_after(s,mo.start_time,12)
    next_m=mo+1
    if next_m.start_time<=pd.Timestamp(date.today()):end,_=first_on_or_after(s,next_m.start_time,12)
    elif last_partial:
        q=s[s.index>=mo.start_time];end=float(q.iloc[-1]) if len(q) else None
    else:end=None
    return end/start-1 if finite(start) and finite(end) and start>0 else None

def debt_return(mo,db_m,db_nav,rates):
    if mo in db_m.index:
        return fs.sleeve_return(mo,db_m,db_nav)
    rate=rates.get(mo-1,np.nan)
    if not pd.notna(rate):return None
    if mo==pd.Period(date.today(),freq='M'):
        days=max(0,(date.today()-mo.start_time.date()).days);return fs.rate_return(rate,days)
    return fs.rate_return(rate)

def metrics(months,rets,weights,cost_bps=0):
    wealth=1.0;curve=[];prev=None;net_rets=[];turns=[]
    for mo,r,w in zip(months,rets,weights):
        if not finite(r):continue
        turn=0 if prev is None else .5*sum(abs(float(w.get(k,0))-float(prev.get(k,0))) for k in set(w)|set(prev))
        rn=float(r)-turn*(cost_bps/10000);wealth*=1+rn;curve.append((mo,wealth));net_rets.append((mo,rn));turns.append(turn);prev=w
    if not curve:return None
    start=months[0].start_time;end=pd.Timestamp(date.today());yrs=max((end-start).days/365.2425,1/12)
    vals=pd.Series([v for _,v in curve],index=[m.to_timestamp() for m,_ in curve]);dd=vals/vals.cummax()-1
    rs=pd.Series([r for _,r in net_rets],index=[m.to_timestamp() for m,_ in net_rets]);ann=rs.groupby(rs.index.year).apply(lambda x:(1+x).prod()-1)
    worst_year=int(ann.idxmin());worst=float(ann.min())
    vol=float(rs.std(ddof=1)*math.sqrt(12)) if len(rs)>1 else None
    return {'multiple_x':wealth,'ending_value_of_1cr_inr':wealth*1e7,'cagr_pct':100*(wealth**(1/yrs)-1),'max_drawdown_pct':100*float(dd.min()),'annualized_volatility_pct':100*vol if finite(vol) else None,'worst_calendar_year':worst_year,'worst_calendar_year_return_pct':100*worst,'average_monthly_turnover_pct':100*float(np.mean(turns)) if turns else 0,'months':len(rs),'cost_bps_per_one_way_turnover':cost_bps}

def build():
    alloc=pd.read_csv(ALLOC);alloc['month']=pd.to_datetime(alloc.Date).dt.to_period('M');alloc=alloc.set_index('month')
    tri=fs.nifty_tri_daily();tri_m=first_monthly(tri);db_nav,_=fs.mf_history(fs.DEBT_CODE);db_m=first_monthly(db_nav);rates=fs.short_rate_monthly()
    gold=yahoo_history('GC=F','1999-01-01');silver=yahoo_history('SI=F','1999-01-01');btc=yahoo_history('BTC-USD','2014-01-01');mac=build_macro()
    gold_inr=inr_series(gold,mac['fx']);silver_inr=inr_series(silver,mac['fx']);btc_inr=inr_series(btc,mac['fx'])
    months=pd.period_range('2000-01',pd.Period(date.today(),freq='M'),freq='M')
    results={'baseline':[],'multiasset_core':[],'multiasset_with_btc':[],'nifty100':[]};weights={k:[] for k in results};used=[];rows=[];first_metals=None;first_btc=None
    for mo in months:
        if mo not in alloc.index:continue
        er=monthly_return(tri,mo);dr=debt_return(mo,db_m,db_nav,rates);gr=monthly_return(gold_inr,mo);sr=monthly_return(silver_inr,mo);br=monthly_return(btc_inr,mo)
        if not all(finite(x) for x in (er,dr)):continue
        eq=float(alloc.loc[mo,'Equity %'])/100;debt=1-eq;sig_date=first_on_or_after(tri,mo.start_time,12)[1] or mo.start_time
        gt=gold_target(gold,mac,sig_date);st=silver_target(gold,silver,mac,sig_date)
        if gt and st and finite(gr) and finite(sr):
            g=gt['target']/100;s=st['target']/100;retained=1-g-s;we=eq*retained;wd=debt*retained
            if first_metals is None:first_metals=str(mo)
        else:g=s=0.0;we=eq;wd=debt
        core_w={'equity':we,'debt':wd,'gold':g,'silver':s};core_r=we*er+wd*dr+g*(gr if finite(gr) else 0)+s*(sr if finite(sr) else 0)
        bt=btc_target(btc,mac,sig_date)
        if bt and finite(br):
            bw=bt['target']/100;btc_w={k:v*(1-bw) for k,v in core_w.items()};btc_w['btc']=bw;btc_r=(1-bw)*core_r+bw*br
            if bw>0 and first_btc is None:first_btc=str(mo)
        else:btc_w=dict(core_w,btc=0.0);btc_r=core_r
        base_w={'equity':eq,'debt':debt};base_r=eq*er+debt*dr
        results['baseline'].append(base_r);weights['baseline'].append(base_w)
        results['multiasset_core'].append(core_r);weights['multiasset_core'].append(core_w)
        results['multiasset_with_btc'].append(btc_r);weights['multiasset_with_btc'].append(btc_w)
        results['nifty100'].append(er);weights['nifty100'].append({'equity':1.0})
        used.append(mo);rows.append({'month':str(mo),'base_equity_pct':100*eq,'gold_pct':100*g,'silver_pct':100*s,'btc_funded_test_pct':100*btc_w.get('btc',0),'core_equity_pct':100*we,'core_debt_pct':100*wd,'baseline_return_pct':100*base_r,'multiasset_core_return_pct':100*core_r,'multiasset_with_btc_return_pct':100*btc_r})
    if len(used)<250:raise RuntimeError(f'Insufficient backtest months {len(used)}')
    perf={};
    for key in results:
        perf[key]={'gross':metrics(used,results[key],weights[key],0),'turnover_10bps':metrics(used,results[key],weights[key],10)}
    out={'status':'complete','generated_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'start_month':str(used[0]),'end_month':str(used[-1]),'months':len(used),'first_month_metals_model_eligible':first_metals,'first_month_btc_funded_test_active':first_btc,
      'performance':perf,'methodology':{
        'base_signal':'data/backtest_monthly_2000.csv common-history NIFTY valuation reconstruction',
        'equity_return':'NIFTY 50 TRI','debt_return':'ICICI Prudential Short Term Fund Regular Growth where available; prior-month India short-rate proxy before NAV history',
        'gold_silver_returns':'Yahoo continuous USD futures converted to synthetic INR with FRED DEXINUS; not ETF total return',
        'gold_signal':'research-v1 live formula: US 10Y real yield 35%, broad USD 3m 25%, gold 12m momentum 25%, VIX 15%; target 8-18%',
        'silver_signal':'research-v1 live formula: gold/silver ratio 45%, China NBS PMI 30%, silver 12m momentum 25%; target 0-7%',
        'metals_activation':'0% until both Gold and Silver models are simultaneously eligible; remaining equity/debt ratio preserved',
        'btc_signal':'research-v1 live formula using 200d trend, 12m momentum, reconstructed global liquidity, 3y drawdown value; 0/2.5/5/7.5/10%',
        'btc_policy':'multiasset_with_btc is research-only and funds BTC by proportional haircut to the 100% core. Live retirement policy keeps BTC outside the core.',
        'lookahead':'signals use only observations dated on/before the monthly signal date; China PMI uses the prior-month reading. Historical macro series are latest-revised, not release-vintage.',
        'taxes_loads_expenses':'excluded','turnover_sensitivity':'10 bps per one-way portfolio turnover reported separately'},'timeline':rows}
    OUT.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8');return out

if __name__=='__main__':
    x=build();print(json.dumps({'status':x['status'],'months':x['months'],'metals_from':x['first_month_metals_model_eligible'],'btc_from':x['first_month_btc_funded_test_active'],'performance':{k:{'ending_cr':round(v['gross']['ending_value_of_1cr_inr']/1e7,2),'cagr':round(v['gross']['cagr_pct'],2),'maxdd':round(v['gross']['max_drawdown_pct'],2)} for k,v in x['performance'].items()}}))
