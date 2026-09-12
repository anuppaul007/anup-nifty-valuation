#!/usr/bin/env python3
"""Prospective, no-lookahead validation ledger for Anup Nifty Valuation.

This file deliberately does NOT optimize or change live model parameters. It
records one evolving snapshot per calendar month from the fully verified V3.6
model, freezes that snapshot when the month changes, and later attaches 6m/12m
NIFTY price returns using only subsequently observed monthly snapshots.

Candidate macro caps, curve slopes and extreme thresholds are recorded from the
same live signal so future evidence can be compared without rewriting history.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import json,math
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
LATEST=ROOT/'data'/'latest.json'
OUT=ROOT/'data'/'walkforward.json'

C={'peM':22.44,'peS':2.08,'pbM':3.88,'pbS':.45,'roeM':17.36,'roeS':1.92,
   'dyM':1.25,'dyS':.18,'gapM':-2.60,'gapS':.70,'beta':.60,'k':1.35,
   'zc':2.5,'earnMax':6.0,'macroMax':6.0}
CANDIDATE_MACRO_CAPS=[0,3,6,9,12,15]
CANDIDATE_CURVE_SLOPES=[.60,.80,1.00,1.15,1.35,1.50]
CANDIDATE_EXTREMES=[2.5,3.0,3.5,4.0]
MIN_SIGNAL_MONTHS=84
MIN_REALIZED_12M=60


def finite(x):
    try:return x is not None and math.isfinite(float(x))
    except (TypeError,ValueError):return False

def clip(x,a,b):return max(a,min(b,float(x)))
def curve(z,k=None,zc=None):
    k=C['k'] if k is None else float(k);zc=C['zc'] if zc is None else float(zc)
    f=lambda x:100/(1+math.exp(k*x));lo=f(zc);hi=f(-zc)
    return clip((f(z)-lo)/(hi-lo)*100,0,100)
def add_month(month,n):return str(pd.Period(month,freq='M')+n)

def model_snapshot(d):
    n=d.get('nifty') or {};m=d.get('macro') or {};e=d.get('earnings') or {}
    required=['level','pe','pb','div_yield','gsec10']
    if d.get('model_version')!='3.6' or any(not finite(n.get(k)) for k in required):return None
    if not finite(m.get('score')) or float(m.get('active_block_weight') or 0)<.999:return None
    if not finite(e.get('score')) or float(e.get('coverage') or 0)<.999:return None
    dom=m.get('domestic') or {}
    if dom.get('status')!='live' or not finite(dom.get('score')):return None
    pe,pb,dy,gsec=map(float,(n['pe'],n['pb'],n['div_yield'],n['gsec10']))
    roe=100*pb/pe;gap=100/pe-gsec
    lenses=[((pe-C['peM'])/C['peS'],30),((pb-C['pbM'])/C['pbS']-C['beta']*(roe-C['roeM'])/C['roeS'],25),(-(gap-C['gapM'])/C['gapS'],30),(-(dy-C['dyM'])/C['dyS'],10)]
    z=sum(v*w for v,w in lenses)/sum(w for _,w in lenses);core=curve(z);damp=clip(1-abs(z)/C['zc'],0,1)
    ea=clip(e['score'],-1,1)*C['earnMax']*damp;ms=clip(m['score'],-1,1)
    macro_candidates={str(cap):clip(core+ea+ms*cap*damp,0,100) for cap in CANDIDATE_MACRO_CAPS}
    curve_candidates={str(k):clip(curve(z,k,C['zc'])+ea+ms*C['macroMax']*damp,0,100) for k in CANDIDATE_CURVE_SLOPES}
    extreme_candidates={str(zc):clip(curve(z,C['k'],zc)+ea+ms*C['macroMax']*damp,0,100) for zc in CANDIDATE_EXTREMES}
    grid_candidates={f'k={k:.2f}|zc={zc:.1f}':clip(curve(z,k,zc)+ea+ms*C['macroMax']*damp,0,100) for zc in CANDIDATE_EXTREMES for k in CANDIDATE_CURVE_SLOPES}
    vd=d.get('valuation_diagnostics') or {}
    return {
      'month':str(n['date'])[:7],'asof':n['date'],'generated_at':d.get('generated_at'),
      'nifty_level':float(n['level']),'pe':pe,'pb':pb,'dividend_yield':dy,'gsec10':gsec,
      'valuation_z':z,'core_equity':core,'valuation_damping':damp,
      'empirical_valuation_cheapness':float(vd['composite_cheapness']) if finite(vd.get('composite_cheapness')) else None,
      'earnings_score':float(e['score']),'macro_score':float(m['score']),'domestic_score':float(dom['score']),
      'macro_blocks':{k:float(v) for k,v in (m.get('blocks') or {}).items() if finite(v)},
      'candidate_equity_targets':macro_candidates,'candidate_curve_targets':curve_candidates,
      'candidate_extreme_targets':extreme_candidates,'candidate_grid_targets':grid_candidates,
      'forward_nifty_price_return_6m':None,'forward_nifty_price_return_12m':None,'outcome_status':'awaiting_future_data'
    }

def update_outcomes(records,current_month):
    by={r['month']:r for r in records}
    for r in records:
        for horizon,key in [(6,'forward_nifty_price_return_6m'),(12,'forward_nifty_price_return_12m')]:
            target=add_month(r['month'],horizon)
            if target>=current_month:continue
            later=by.get(target)
            if later and finite(later.get('nifty_level')) and finite(r.get('nifty_level')) and r['nifty_level']>0:r[key]=100*(float(later['nifty_level'])/float(r['nifty_level'])-1)
        r['outcome_status']='12m_realized' if finite(r.get('forward_nifty_price_return_12m')) else ('6m_realized' if finite(r.get('forward_nifty_price_return_6m')) else 'awaiting_future_data')
    return records

def summary(records):
    realized6=sum(finite(r.get('forward_nifty_price_return_6m')) for r in records);realized12=sum(finite(r.get('forward_nifty_price_return_12m')) for r in records)
    eligible=len(records)>=MIN_SIGNAL_MONTHS and realized12>=MIN_REALIZED_12M
    return {'status':'eligible_for_review' if eligible else 'collecting_prospective_data','signal_months':len(records),'realized_6m_outcomes':realized6,'realized_12m_outcomes':realized12,
      'required_signal_months':MIN_SIGNAL_MONTHS,'required_realized_12m_outcomes':MIN_REALIZED_12M,'eligible_for_parameter_change':eligible,
      'parameter_lock':'macroMax=6 pp, curve k=1.35 and extreme threshold zc=2.5 remain locked until prospective evidence gate is satisfied',
      'note':'Forward returns are NIFTY price-index returns only. Candidate settings are recorded prospectively and never auto-selected from future outcomes.'}

def main():
    d=json.loads(LATEST.read_text())
    try:w=json.loads(OUT.read_text())
    except (OSError,ValueError):w={'schema_version':1,'records':[]}
    records=[r for r in w.get('records',[]) if isinstance(r,dict) and r.get('month')]
    snap=model_snapshot(d);current_month=str(pd.Period(datetime.now(timezone.utc).date(),freq='M'))
    if snap:
        records=[r for r in records if r['month']!=snap['month']];records.append(snap)
    records=sorted(records,key=lambda r:r['month'])[-180:];records=update_outcomes(records,current_month)
    out={'schema_version':2,'model_version':'3.6','updated_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
         'candidate_macro_caps_pp':CANDIDATE_MACRO_CAPS,'candidate_curve_slopes':CANDIDATE_CURVE_SLOPES,'candidate_extreme_thresholds':CANDIDATE_EXTREMES,
         'validation':summary(records),'records':records}
    tmp=OUT.with_suffix('.tmp');tmp.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8');tmp.replace(OUT)
    print(json.dumps(out['validation']))
if __name__=='__main__':main()
