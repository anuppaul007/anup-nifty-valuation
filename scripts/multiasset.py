#!/usr/bin/env python3
"""Experimental multi-asset layer for Anup Nifty Valuation.

This module sits *above* the existing NIFTY equity/debt model. It never changes
model.js or the V3.6 NIFTY signal. Instead it:

1. Reconstructs the current NIFTY equity/debt research signal from latest.json.
2. Builds independent Gold and Silver attractiveness scores from dated market
   and macro inputs.
3. Carves Gold/Silver proportionally from the NIFTY equity/debt mix so the
   retirement-core allocation still sums to 100%.
4. Publishes Bitcoin only as a separate tactical signal. BTC is NOT deducted
   from the retirement-core 100% allocation.

The layer is deliberately conservative about missing data: if a required input
is stale or missing, the affected allocation is withheld rather than neutral-
filled. Parameters are transparent research assumptions and are not backtest-
optimized.
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from pathlib import Path
import json, math, subprocess
import numpy as np
import pandas as pd
import macro_v3 as macro

ROOT=Path(__file__).resolve().parents[1]
LATEST=ROOT/'data'/'latest.json'
OUT=ROOT/'data'/'multiasset.json'

# Must remain aligned with model.js. This file does not modify the live model.
C={'peM':22.44,'peS':2.08,'pbM':3.88,'pbS':.45,'roeM':17.36,'roeS':1.92,
   'dyM':1.25,'dyS':.18,'gapM':-2.60,'gapS':.70,'beta':.60,'k':1.35,
   'zc':2.5,'earnMax':6.0,'macroMax':6.0}


def finite(x):
    try:return x is not None and math.isfinite(float(x))
    except (TypeError,ValueError):return False

def clip(x,a,b):return max(a,min(b,float(x)))
def squash(x,scale=1.0):return float(np.tanh(float(x)/float(scale)))
def curve(z):
    f=lambda x:100/(1+math.exp(C['k']*x));lo=f(C['zc']);hi=f(-C['zc'])
    return clip((f(z)-lo)/(hi-lo)*100,0,100)

def age_days(s):
    try:return (date.today()-date.fromisoformat(str(s)[:10])).days
    except Exception:return 10**9

def clean_market(df,name,max_age=7):
    if df is None or len(df)<260:raise RuntimeError(f'{name}: insufficient market history')
    q=df.copy().sort_values('date').dropna()
    if age_days(q.attrs.get('asof'))>max_age:raise RuntimeError(f'{name}: stale market observation')
    s=q.set_index('date').value.astype(float).sort_index()
    if len(s)<260 or not finite(s.iloc[-1]) or s.iloc[-1]<=0:raise RuntimeError(f'{name}: invalid latest price')
    return q,s

def value_near_or_before(s,when,max_days=15):
    q=s[(s.index<=when)&(s.index>=when-pd.Timedelta(days=max_days))]
    return float(q.iloc[-1]) if len(q) else None

def price_features(df,name,max_age=7):
    q,s=clean_market(df,name,max_age)
    px=float(s.iloc[-1]);last=pd.Timestamp(s.index[-1]);ma200=float(s.iloc[-200:].mean())
    prior=value_near_or_before(s,last-pd.DateOffset(years=1),20)
    if prior is None or prior<=0:raise RuntimeError(f'{name}: one-year comparison unavailable')
    mom12=100*(px/prior-1)
    high3=float(s.max());drawdown=100*(px/high3-1)
    return {
      'price':px,'asof':q.attrs.get('asof'),'source_url':q.attrs.get('source'),
      'ma200':ma200,'vs_ma200_pct':100*(px/ma200-1),'momentum_12m_pct':mom12,
      'three_year_high':high3,'drawdown_from_3y_high_pct':drawdown,'observations':int(len(s))
    },s

def latest_core_signal(d):
    # One live authority; legacy C above remains for explicitly legacy research.
    program="const M=require('./model.js'),fs=require('fs');const r=M.calculate(JSON.parse(fs.readFileSync(0,'utf8')));process.stdout.write(JSON.stringify({r,version:M.VERSION}));"
    result=subprocess.run(['node','-e',program],cwd=ROOT,input=json.dumps(d,allow_nan=False),text=True,capture_output=True,check=True)
    payload=json.loads(result.stdout);r=payload['r']
    if not r.get('allocationReady'):raise RuntimeError('NIFTY live model withheld: '+str(r.get('holdReason') or r.get('reason')))
    return {'equity_pct':r['final'],'debt_pct':100-r['final'],'valuation_z':r['z'],'core_pct':r['core'],
            'earnings_adjustment_pp':r['ea'],'macro_adjustment_pp':r['ma'],'model_version':payload['version']}

def require_macro_factor(d,key,max_age):
    m=d.get('macro') or {};f=(m.get('factors') or {}).get(key) or {}
    if f.get('status')!='live' or not finite(f.get('value')) or age_days(f.get('asof'))>max_age:
        raise RuntimeError(f'macro factor unavailable: {key}')
    return float(f['value']),f

def gold_model(d,gold):
    real,rf=require_macro_factor(d,'us_real_10y',7);usd,uf=require_macro_factor(d,'usd_3m_pct',75);vix,vf=require_macro_factor(d,'vix',7)
    real_score=squash(-(real-1.5),1.25)
    usd_score=squash(-usd,4.0)
    trend_score=squash(gold['momentum_12m_pct'],20.0)
    stress_score=squash(vix-20,10.0)
    score=.35*real_score+.25*usd_score+.25*trend_score+.15*stress_score
    target=clip(13+5*score,8,18)
    return {'score':score,'target_pct':target,'range_pct':[8,18],'drivers':{
      'real_yield':{'value':real,'score':real_score,'weight':.35,'asof':rf.get('asof')},
      'broad_usd_3m':{'value':usd,'score':usd_score,'weight':.25,'asof':uf.get('asof')},
      'gold_12m_momentum':{'value':gold['momentum_12m_pct'],'score':trend_score,'weight':.25,'asof':gold['asof']},
      'vix_stress':{'value':vix,'score':stress_score,'weight':.15,'asof':vf.get('asof')}
    }}

def ratio_score(gold_s,silver_s):
    x=pd.concat([gold_s.rename('g'),silver_s.rename('s')],axis=1).dropna();x=x[(x.g>0)&(x.s>0)]
    if len(x)<260:raise RuntimeError('gold/silver ratio: insufficient overlap')
    ratio=x.g/x.s;current=float(ratio.iloc[-1]);hist=ratio.iloc[:-1].tail(756);sd=float(hist.std(ddof=0))
    if len(hist)<250 or not finite(sd) or sd<1e-9:raise RuntimeError('gold/silver ratio: invalid history')
    z=clip((current-float(hist.mean()))/sd,-3,3)
    return current,z,squash(z,1.5),int(len(hist))

def silver_model(d,silver,gold_s,silver_s):
    ch=(d.get('macro') or {}).get('china_pmi') or {}
    if ch.get('status')!='live' or float(ch.get('coverage') or 0)<.999 or not finite(ch.get('score')) or age_days(ch.get('asof'))>70:
        raise RuntimeError('China industrial factor unavailable')
    ratio,z,rel_score,nobs=ratio_score(gold_s,silver_s);industrial=float(ch['score']);trend=squash(silver['momentum_12m_pct'],30.0)
    score=.45*rel_score+.30*industrial+.25*trend;target=clip(3.5+3.5*score,0,7)
    return {'score':score,'target_pct':target,'range_pct':[0,7],'drivers':{
      'gold_silver_ratio':{'value':ratio,'z':z,'score':rel_score,'weight':.45,'observations':nobs},
      'china_industrial':{'value':float(ch.get('pmi')),'score':industrial,'weight':.30,'asof':ch.get('asof')},
      'silver_12m_momentum':{'value':silver['momentum_12m_pct'],'score':trend,'weight':.25,'asof':silver['asof']}
    }}

def btc_model(d,btc):
    m=d.get('macro') or {};liq=(m.get('blocks') or {}).get('global_liquidity')
    if not finite(liq):raise RuntimeError('global liquidity block unavailable')
    trend=squash(btc['vs_ma200_pct'],20.0);mom=squash(btc['momentum_12m_pct'],60.0)
    value=squash((-btc['drawdown_from_3y_high_pct'])-25,20.0)
    score=.30*trend+.20*mom+.25*float(liq)+.25*value
    if score<-.50:target=0.0
    elif score<-.15:target=2.5
    elif score<.25:target=5.0
    elif score<.55:target=7.5
    else:target=10.0
    return {'score':score,'tactical_signal_pct':target,'range_pct':[0,10],'included_in_core_100pct':False,'drivers':{
      'price_vs_200d':{'value':btc['vs_ma200_pct'],'score':trend,'weight':.30,'asof':btc['asof']},
      'btc_12m_momentum':{'value':btc['momentum_12m_pct'],'score':mom,'weight':.20,'asof':btc['asof']},
      'global_liquidity':{'value':float(liq),'score':float(liq),'weight':.25,'asof':d.get('generated_at')},
      'drawdown_value':{'value':btc['drawdown_from_3y_high_pct'],'score':value,'weight':.25,'asof':btc['asof']}
    }}

def build(d=None,market=None):
    d=d or json.loads(LATEST.read_text())
    source_latest_generated_at=d.get('generated_at')
    if not isinstance(source_latest_generated_at,str) or not source_latest_generated_at:
        raise RuntimeError('latest.json snapshot timestamp missing')
    core=latest_core_signal(d)
    if market is None:market={'gold':macro.yahoo_series('GC=F'),'silver':macro.yahoo_series('SI=F'),'btc':macro.yahoo_series('BTC-USD')}
    gold,gold_s=price_features(market['gold'],'gold',7);silver,silver_s=price_features(market['silver'],'silver',7);btc,_=price_features(market['btc'],'BTC',3)
    gm=gold_model(d,gold);sm=silver_model(d,silver,gold_s,silver_s);bm=btc_model(d,btc)
    alt=clip(gm['target_pct']+sm['target_pct'],0,25);retained=(100-alt)/100
    allocation={'equity_pct':core['equity_pct']*retained,'debt_pct':core['debt_pct']*retained,'gold_pct':gm['target_pct'],'silver_pct':sm['target_pct']}
    total=sum(allocation.values())
    if abs(total-100)>1e-8:raise RuntimeError(f'core allocation does not sum to 100: {total}')
    return {
      'schema_version':1,'model_version':'multiasset-research-v1','generated_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'status':'live',
      'source_latest_generated_at':source_latest_generated_at,
      'core_source':'V3.6 NIFTY equity/debt research signal; gold and silver are a diversification layer carved proportionally from both sleeves',
      'core_signal_before_metals':core,'core_allocation':allocation,'core_total_pct':total,
      'gold':dict(gm,market=gold),'silver':dict(sm,market=silver),'btc':dict(bm,market=btc),
      'btc_policy':'Separate tactical signal only. It is excluded from the retirement-core 100% allocation and is not funded by mechanically reducing the core portfolio.',
      'assumptions':{'gold_target_rule':'13% + 5% × score, clipped to 8–18%','silver_target_rule':'3.5% + 3.5% × score, clipped to 0–7%','metals_total_cap_pct':25,'btc_signal_steps_pct':[0,2.5,5,7.5,10],'optimization':'None. Parameters are transparent research assumptions pending dedicated historical validation.'},
      'sources':[{'name':'Yahoo Finance Gold futures','symbol':'GC=F','url':gold['source_url']},{'name':'Yahoo Finance Silver futures','symbol':'SI=F','url':silver['source_url']},{'name':'Yahoo Finance Bitcoin USD','symbol':'BTC-USD','url':btc['source_url']},{'name':'Existing V3.6 macro packet','role':'US real yield, broad USD, VIX, global liquidity and China industrial cycle'}]
    }

def main():
    source_latest_generated_at=None
    try:source_latest_generated_at=json.loads(LATEST.read_text()).get('generated_at')
    except Exception:pass
    try:out=build()
    except Exception as e:out={'schema_version':1,'model_version':'multiasset-research-v1','generated_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'status':'withheld','source_latest_generated_at':source_latest_generated_at,'error':f'{type(e).__name__}: {e}','core_allocation':None,'btc':None}
    tmp=OUT.with_suffix('.tmp');tmp.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8');tmp.replace(OUT)
    print(json.dumps({'status':out.get('status'),'source_latest_generated_at':out.get('source_latest_generated_at'),'core_allocation':out.get('core_allocation'),'btc_signal':(out.get('btc') or {}).get('tactical_signal_pct')}))
    if out.get('status')!='live':raise RuntimeError(out.get('error','multiasset build withheld'))

if __name__=='__main__':main()
