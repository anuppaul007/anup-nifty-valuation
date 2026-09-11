#!/usr/bin/env python3
"""Prospective, no-lookahead validation ledger for Anup Nifty Valuation.

This file deliberately does NOT optimize or change live model parameters. It
records one evolving snapshot per calendar month from the fully verified V3.6
model, freezes that snapshot when the month changes, and later attaches 6m/12m
NIFTY price returns using only subsequently observed monthly snapshots.

Why prospective? Current CPI/IIP and several valuation/macro series have had
methodology/base revisions. Retrofitting today's complete model onto old data
would create a false sense of precision. The ledger therefore provides a clean
out-of-sample record before any macro overlay cap can be changed.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import json,math
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
LATEST=ROOT/'data'/'latest.json'
OUT=ROOT/'data'/'walkforward.json'

# Must stay in sync with model.js. Any future change should update the test.
C={'peM':22.44,'peS':2.08,'pbM':3.88,'pbS':.45,'roeM':17.36,'roeS':1.92,
   'dyM':1.25,'dyS':.18,'gapM':-2.60,'gapS':.70,'beta':.60,'k':1.35,
   'zc':2.5,'earnMax':6.0}
CANDIDATE_MACRO_CAPS=[0,3,6,9,12,15]
MIN_SIGNAL_MONTHS=84
MIN_REALIZED_12M=60


def finite(x):
    try:return x is not None and math.isfinite(float(x))
    except (TypeError,ValueError):return False

def clip(x,a,b):return max(a,min(b,float(x)))
def curve(z):
    f=lambda x:100/(1+math.exp(C['k']*x));lo=f(C['zc']);hi=f(-C['zc'])
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
    lenses=[
      ((pe-C['peM'])/C['peS'],30),
      ((pb-C['pbM'])/C['pbS']-C['beta']*(roe-C['roeM'])/C['roeS'],25),
      (-(gap-C['gapM'])/C['gapS'],30),
      (-(dy-C['dyM'])/C['dyS'],10),
    ]
    z=sum(v*w for v,w in lenses)/sum(w for _,w in lenses);core=curve(z);damp=clip(1-abs(z)/C['zc'],0,1)
    ea=clip(e['score'],-1,1)*C['earnMax']*damp
    candidates={str(cap):clip(core+ea+clip(m['score'],-1,1)*cap*damp,0,100) for cap in CANDIDATE_MACRO_CAPS}
    return {
      'month':str(n['date'])[:7],'asof':n['date'],'generated_at':d.get('generated_at'),
      'nifty_level':float(n['level']),'pe':pe,'pb':pb,'div_yield':dy,'gsec10':gsec,
      'valuation_z':z,'core_equity':core,'valuation_damping':damp,
      'earnings_score':float(e['score']),'macro_score':float(m['score']),
      'domestic_score':float(dom['score']),
      'macro_blocks':{k:float(v) for k,v in (m.get('blocks') or {}).items() if finite(v)},
      'candidate_equity_targets':candidates,
      'forward_nifty_price_return_6m':None,'forward_nifty_price_return_12m':None,
      'outcome_status':'awaiting_future_data'
    }

def update_outcomes(records,current_month):
    by={r['month']:r for r in records}
    for r in records:
        for horizon,key in [(6,'forward_nifty_price_return_6m'),(12,'forward_nifty_price_return_12m')]:
            target=add_month(r['month'],horizon)
            # A target month must be complete; never use a partial current month as outcome.
            if target>=current_month:continue
            later=by.get(target)
            if later and finite(later.get('nifty_level')) and finite(r.get('nifty_level')) and r['nifty_level']>0:
                r[key]=100*(float(later['nifty_level'])/float(r['nifty_level'])-1)
        r['outcome_status']='12m_realized' if finite(r.get('forward_nifty_price_return_12m')) else ('6m_realized' if finite(r.get('forward_nifty_price_return_6m')) else 'awaiting_future_data')
    return records

def summary(records):
    realized6=sum(finite(r.get('forward_nifty_price_return_6m')) for r in records)
    realized12=sum(finite(r.get('forward_nifty_price_return_12m')) for r in records)
    eligible=len(records)>=MIN_SIGNAL_MONTHS and realized12>=MIN_REALIZED_12M
    return {
      'status':'eligible_for_review' if eligible else 'collecting_prospective_data',
      'signal_months':len(records),'realized_6m_outcomes':realized6,'realized_12m_outcomes':realized12,
      'required_signal_months':MIN_SIGNAL_MONTHS,'required_realized_12m_outcomes':MIN_REALIZED_12M,
      'eligible_for_parameter_change':eligible,
      'parameter_lock':'macroMax remains 6 pp until prospective evidence gate is satisfied',
      'note':'Forward returns are NIFTY price-index returns only. They are not debt-relative portfolio returns and are not used to auto-optimize the live model.'
    }

def main():
    d=json.loads(LATEST.read_text())
    try:w=json.loads(OUT.read_text())
    except (OSError,ValueError):w={'schema_version':1,'records':[]}
    records=[r for r in w.get('records',[]) if isinstance(r,dict) and r.get('month')]
    snap=model_snapshot(d);current_month=str(pd.Period(datetime.now(timezone.utc).date(),freq='M'))
    if snap:
        # Update only the current month's record. Older months are immutable signals.
        records=[r for r in records if r['month']!=snap['month']]
        records.append(snap)
    records=sorted(records,key=lambda r:r['month'])[-180:]
    records=update_outcomes(records,current_month)
    out={'schema_version':1,'model_version':'3.6','updated_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
         'candidate_macro_caps_pp':CANDIDATE_MACRO_CAPS,'validation':summary(records),'records':records}
    tmp=OUT.with_suffix('.tmp');tmp.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8');tmp.replace(OUT)
    print(json.dumps(out['validation']))
if __name__=='__main__':main()
