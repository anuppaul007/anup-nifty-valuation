#!/usr/bin/env python3
"""Episode-level payout audit for the frozen SMA10 -20pp crash brake.

This is insurance attribution, not parameter search. It deliberately tests only
the already-frozen -20pp rule. No -10/-30/continuous alternatives are tried, so
this audit does not create a new trend-parameter selection family.

The five largest drawdown episodes are defined from the unbraked legacy
valuation-core portfolio on the longest exact shared NIFTY/debt history. Each
episode is then replayed against the already-frozen braked portfolio over the
same dates.
"""
from __future__ import annotations

from pathlib import Path
import json
import math
import pandas as pd

import trend_challenger_backtest_v2 as v2

# v2 swaps only the debt loader for the exact fixed-income index source.
a=v2.a
a.debt_tri_daily=v2.debt_tri_daily
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'sma10_episode_audit.json'


def finite(x):
    try:return x is not None and math.isfinite(float(x))
    except (TypeError,ValueError):return False


def drawdown_episodes(df):
    """Return non-overlapping peak/trough/recovery episodes from portfolio NAV."""
    v=df.value.astype(float)
    if len(v)<2:return []
    peak_date=v.index[0];peak_value=float(v.iloc[0])
    active=None;episodes=[]
    for dt,val0 in v.items():
        val=float(val0)
        if val>=peak_value:
            if active is not None:
                active['recovery_date']=dt
                active['recovery_value']=val
                episodes.append(active)
                active=None
            peak_date=dt;peak_value=val
            continue
        if active is None:
            active={
              'peak_date':peak_date,'peak_value':peak_value,
              'trough_date':dt,'trough_value':val,
              'recovery_date':None,'recovery_value':None,
            }
        elif val<active['trough_value']:
            active['trough_date']=dt;active['trough_value']=val
    if active is not None:episodes.append(active)
    for e in episodes:
        e['drawdown_pct']=100*(e['trough_value']/e['peak_value']-1)
    return episodes


def state_transitions(execs):
    q=execs[['risk_off']].copy();q['risk_off']=q.risk_off.astype(bool)
    q['prev']=q.risk_off.shift(1)
    return q[(q.prev.isna())|(q.risk_off!=q.prev)]


def state_on(execs,dt):
    q=execs.loc[execs.index<=dt]
    return bool(q.iloc[-1].risk_off) if len(q) else False


def transition_into_before(transitions,dt):
    q=transitions[(transitions.index<=dt)&(transitions.risk_off==True)]
    return q.index[-1] if len(q) else None


def transition_after(transitions,dt,to_state):
    q=transitions[(transitions.index>dt)&(transitions.risk_off==bool(to_state))]
    return q.index[0] if len(q) else None


def first_riskoff_between(transitions,start,end):
    q=transitions[(transitions.index>=start)&(transitions.index<=end)&(transitions.risk_off==True)]
    return q.index[0] if len(q) else None


def rebase_drawdown(df,start,end):
    q=df.loc[start:end].value.astype(float)
    if len(q)<2:return None
    base=float(q.iloc[0])
    return 100*float((q/base-1).min())


def recovery_block(df,trough,market_end):
    end=min(pd.Timestamp(trough)+pd.DateOffset(months=12),pd.Timestamp(market_end))
    q=df.loc[trough:end]
    if len(q)<2:return {'end':str(end.date()),'return_pct':None,'average_equity_pct':None,'trading_days':int(len(q))}
    return {
      'end':str(q.index[-1].date()),
      'return_pct':100*(float(q.value.iloc[-1]/q.value.iloc[0])-1),
      'average_equity_pct':100*float(q.equity_weight.mean()),
      'trading_days':int(len(q)),
    }


def episode_row(rank,e,b,c,execs,transitions,market_end):
    peak=pd.Timestamp(e['peak_date']);trough=pd.Timestamp(e['trough_date'])
    recovery=pd.Timestamp(e['recovery_date']) if e['recovery_date'] is not None else None
    active_at_peak=state_on(execs,peak)
    if active_at_peak:
        engage=transition_into_before(transitions,peak)
    else:
        engage=first_riskoff_between(transitions,peak,trough)
    disengage=transition_after(transitions,engage,False) if engage is not None else None
    bdd=rebase_drawdown(b,peak,trough);cdd=rebase_drawdown(c,peak,trough)
    br=recovery_block(b,trough,market_end);cr=recovery_block(c,trough,market_end)
    return {
      'rank':rank,
      'baseline_peak_date':str(peak.date()),
      'baseline_trough_date':str(trough.date()),
      'baseline_recovery_date':str(recovery.date()) if recovery is not None else None,
      'baseline_full_episode_drawdown_pct':float(e['drawdown_pct']),
      'same_window_baseline_drawdown_pct':bdd,
      'same_window_braked_drawdown_pct':cdd,
      'brake_drawdown_payout_pp':(cdd-bdd) if finite(bdd) and finite(cdd) else None,
      'brake_active_at_peak':active_at_peak,
      'brake_engaged_date':str(engage.date()) if engage is not None else None,
      'brake_disengaged_date':str(disengage.date()) if disengage is not None else None,
      'engagement_days_before_trough':int((trough-engage).days) if engage is not None else None,
      'engaged_before_or_on_trough':bool(engage is not None and engage<=trough),
      'recovery_12m':{
        'baseline_return_pct':br['return_pct'],
        'braked_return_pct':cr['return_pct'],
        'braked_minus_baseline_return_pp':(cr['return_pct']-br['return_pct']) if finite(br['return_pct']) and finite(cr['return_pct']) else None,
        'baseline_average_equity_pct':br['average_equity_pct'],
        'braked_average_equity_pct':cr['average_equity_pct'],
        'braked_minus_baseline_average_equity_pp':(cr['average_equity_pct']-br['average_equity_pct']) if finite(br['average_equity_pct']) and finite(cr['average_equity_pct']) else None,
        'through':br['end'],
      },
    }


def covid_timeline(price,execs,transitions):
    start=pd.Timestamp('2020-02-01');end=pd.Timestamp('2020-09-30')
    p=price.loc[start:end]
    trough=p.idxmin();level=float(p.loc[trough])
    t=execs.loc[(execs.index>=start)&(execs.index<=end)]
    rows=[]
    for dt,r in t.iterrows():
        rows.append({
          'execution_date':str(dt.date()),
          'signal_date':str(pd.Timestamp(r.signal_date).date()) if 'signal_date' in r else None,
          'prior_month_close':float(r.prior_month_close),
          'sma10':float(r.sma10),
          'risk_off':bool(r.risk_off),
          'baseline_equity_pct':100*float(r.baseline_target),
          'braked_equity_pct':100*float(r.challenger_target),
          'adjustment_pp':100*(float(r.challenger_target)-float(r.baseline_target)),
        })
    risk_in=transitions[(transitions.index>=start)&(transitions.index<=end)&(transitions.risk_off==True)]
    first=risk_in.index[0] if len(risk_in) else None
    risk_out=transitions[(transitions.index>first)&(transitions.index<=end)&(transitions.risk_off==False)] if first is not None else transitions.iloc[0:0]
    off=risk_out.index[0] if len(risk_out) else None
    return {
      'window':'2020-02-01 through 2020-09-30',
      'nifty_price_trough_date':str(trough.date()),
      'nifty_price_trough_level':level,
      'first_risk_off_transition':str(first.date()) if first is not None else None,
      'first_risk_on_transition_after':str(off.date()) if off is not None else None,
      'risk_off_engaged_before_nifty_trough':bool(first is not None and first<=trough),
      'days_engaged_before_nifty_trough':int((trough-first).days) if first is not None else None,
      'monthly_execution_timeline':rows,
    }


def main():
    policy=a.load_policy();price=a.nifty_price_daily();eq,eqmeta=a.equity_tri_daily();debt,debtmeta=v2.debt_tri_daily()
    decisions,_=a.build_decisions(policy,price);market=a.common_market(eq,debt);execs=a.execution_map(decisions,market)
    b,_,c,_=a.run_variant(market,execs,policy,0.0,0.001)
    episodes=drawdown_episodes(b)
    top=sorted(episodes,key=lambda x:x['drawdown_pct'])[:5]
    transitions=state_transitions(execs)
    rows=[episode_row(i+1,e,b,c,execs,transitions,market.index.max()) for i,e in enumerate(top)]
    covid=covid_timeline(price,execs,transitions)
    payout=[x['brake_drawdown_payout_pp'] for x in rows if finite(x.get('brake_drawdown_payout_pp'))]
    recovery=[x['recovery_12m']['braked_minus_baseline_return_pp'] for x in rows if finite(x['recovery_12m'].get('braked_minus_baseline_return_pp'))]
    out={
      'schema_version':1,
      'status':'complete',
      'policy_id':policy['id'],
      'research_role':'Episode-level insurance payout attribution for the already-frozen -20pp rule. No alternative trend magnitude or continuous rule is tested.',
      'episode_definition':'Five largest non-overlapping peak-to-trough drawdowns of the unbraked legacy valuation-core portfolio on the longest exact shared NIFTY/debt history.',
      'top_five_drawdown_episodes':rows,
      'covid_feb_sep_2020':covid,
      'summary':{
        'episodes_with_positive_drawdown_payout':int(sum(x>0 for x in payout)),
        'episodes_with_negative_drawdown_payout':int(sum(x<0 for x in payout)),
        'median_drawdown_payout_pp':float(pd.Series(payout).median()) if payout else None,
        'episodes_with_lower_12m_recovery_return':int(sum(x<0 for x in recovery)),
        'median_12m_recovery_return_difference_pp':float(pd.Series(recovery).median()) if recovery else None,
      },
      'source_metadata':{'equity':eqmeta,'debt':debtmeta},
      'limitations':[
        'This is a legacy valuation-core insurance attribution, not a historical reconstruction of the full V3.11 stack.',
        'Episodes are selected by baseline portfolio drawdown, so results are descriptive insurance attribution rather than an untouched out-of-sample test.',
        'The audit does not test -10pp, -30pp, dual-SMA, continuous, or any other trend rule. Testing such alternatives would create a new selection family and must carry its own trial burden.',
        'Taxes are excluded and the debt sleeve is the NIFTY 10 YR BENCHMARK G-SEC index.'
      ],
      'live_rule_changed':False,
    }
    OUT.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({
      'top5':[(x['baseline_trough_date'],round(x['baseline_full_episode_drawdown_pct'],2),round(x['brake_drawdown_payout_pp'],2) if finite(x.get('brake_drawdown_payout_pp')) else None) for x in rows],
      'covid':{k:covid[k] for k in ['nifty_price_trough_date','first_risk_off_transition','first_risk_on_transition_after','risk_off_engaged_before_nifty_trough','days_engaged_before_nifty_trough']},
      'summary':out['summary']
    },separators=(',',':')))


if __name__=='__main__':main()
