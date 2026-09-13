#!/usr/bin/env python3
"""Price the frozen SMA10 -20pp brake as insurance, not alpha.

The audit reports the return premium paid beside drawdown protection purchased
on two windows:
1) the same 63 calendar return months used by the current valuation timing audit;
2) the already-verified longest exact shared history preserved in
   data/trend_challenger_summary.json.

The shorter window is freshly recomputed from exact index sources. The longer
window is copied from the frozen, green-CI historical result instead of
re-downloading fifteen years of daily data on every audit run.

Research only: never modifies model.js or live parameters.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
import json
import pandas as pd

import robust_evaluation as re
import retrospective_core as r
import trend_challenger_backtest_v2 as v2

# Importing v2 replaces the original debt loader with the exact frozen fixed-
# income index source. All signal/simulation rules stay in the frozen v1 engine.
a=v2.a
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'sma10_insurance_audit.json'
LONG_SUMMARY=ROOT/'data'/'trend_challenger_summary.json'


def tradeoff(baseline,challenger):
    bm=a.metrics(baseline);cm=a.metrics(challenger)
    return {
      'baseline':bm,'braked':cm,
      'cagr_premium_paid_pp_per_year':float(bm['cagr_pct']-cm['cagr_pct']),
      'max_daily_drawdown_avoided_pp':float(cm['max_daily_drawdown_pct']-bm['max_daily_drawdown_pct']),
      'monthly_expected_shortfall_improvement_pp':float(cm['monthly_expected_shortfall_95_pct']-bm['monthly_expected_shortfall_95_pct']),
      'daily_ulcer_index_improvement_pp':float(bm['daily_ulcer_index_pct']-cm['daily_ulcer_index_pct']),
      'longest_underwater_change_trading_days':int(cm['longest_underwater_trading_days']-bm['longest_underwater_trading_days']),
      'average_equity_reduction_pp':float(bm['average_equity_exposure_pct']-cm['average_equity_exposure_pct']),
      'interpretation':'Positive CAGR premium means return was given up. Positive drawdown/expected-shortfall/Ulcer improvement means path risk improved. Positive underwater change means recovery took longer.'
    }


def long_history_from_frozen_summary():
    q=json.loads(LONG_SUMMARY.read_text(encoding='utf-8'))
    if q.get('policy_id')!='trend-sma10-minus20-v1':raise RuntimeError('Frozen trend summary policy mismatch')
    ref=q.get('reference_variant',{});base=ref.get('baseline',{});brake=ref.get('challenger',{});sample=q.get('exact_shared_sample',{})
    required=['cagr_pct','max_daily_drawdown_pct','monthly_expected_shortfall_95_pct','daily_ulcer_index_pct','longest_underwater_trading_days','average_equity_exposure_pct']
    if not all(k in base and k in brake for k in required):raise RuntimeError('Frozen trend summary incomplete')
    return {
      'source':'data/trend_challenger_summary.json; previously source-corrected green-CI exact-history result',
      'source_green_ci_run':q.get('green_ci_run'),'source_green_artifact_digest':q.get('green_artifact_digest'),
      'first_execution':sample.get('first_execution'),'last_market_date':sample.get('last_market_date'),
      'trend_executions':sample.get('monthly_decisions'),'risk_off_months':sample.get('risk_off_months'),'risk_off_pct':sample.get('risk_off_pct'),
      'baseline':base,'braked':brake,
      'cagr_premium_paid_pp_per_year':float(base['cagr_pct']-brake['cagr_pct']),
      'max_daily_drawdown_avoided_pp':float(brake['max_daily_drawdown_pct']-base['max_daily_drawdown_pct']),
      'monthly_expected_shortfall_improvement_pp':float(brake['monthly_expected_shortfall_95_pct']-base['monthly_expected_shortfall_95_pct']),
      'daily_ulcer_index_improvement_pp':float(base['daily_ulcer_index_pct']-brake['daily_ulcer_index_pct']),
      'longest_underwater_change_trading_days':int(brake['longest_underwater_trading_days']-base['longest_underwater_trading_days']),
      'average_equity_reduction_pp':float(base['average_equity_exposure_pct']-brake['average_equity_exposure_pct']),
      'historical_promotion_hurdle_met':bool(q.get('frozen_gate_assessment',{}).get('historical_result_can_promote_live',False)),
      'interpretation':'Positive CAGR premium means return was given up. Positive drawdown/expected-shortfall/Ulcer improvement means path risk improved. Positive underwater change means recovery took longer.'
    }


def simulate_window(market,execs,policy,start_period,end_period):
    months=pd.period_range(start_period,end_period,freq='M')
    chosen=execs[execs.index.to_period('M').isin(months)].copy()
    if len(chosen)!=len(months):
        missing=[str(m) for m in months if m not in set(chosen.index.to_period('M'))]
        raise RuntimeError(f'Exact monthly trend execution coverage missing for {missing}')
    first=chosen.index.min();last_period=months[-1]
    eligible_end=market.index[market.index.to_period('M')==last_period]
    if len(eligible_end)==0:raise RuntimeError(f'No exact shared market rows in {last_period}')
    last=eligible_end.max();m=market.loc[first:last]
    b,_,c,_=a.run_variant(m,chosen,policy,0.0,0.001)
    return b,c,{
      'calendar_return_months':int(len(months)),
      'first_return_month':str(months[0]),'last_return_month':str(months[-1]),
      'first_execution':str(first.date()),'last_market_date':str(last.date()),
      'trend_executions':int(len(chosen)),'risk_off_months':int(chosen.risk_off.sum()),
      'risk_off_pct':100*float(chosen.risk_off.mean())
    }


def main():
    policy=a.load_policy()
    retro=json.loads((ROOT/'data'/'retrospective.json').read_text(encoding='utf-8'))
    panel=re.panel_from_retrospective(retro);frame,_,_,_=r.strategy_returns(panel,r.LIVE_K,r.LIVE_ZC)
    return_months=pd.PeriodIndex([p+1 for p in frame.index],freq='M')
    if len(return_months)!=63:raise RuntimeError(f'Expected 63 primary timing return months, got {len(return_months)}')

    # Only enough source history for the 10-month lookback before the first
    # primary return month is needed for this fresh comparable-window run.
    a.START=date(2020,1,1)
    price=a.nifty_price_daily();eq,eqmeta=a.equity_tri_daily();debt,debtmeta=v2.debt_tri_daily()
    decisions,_=a.build_decisions(policy,price);market=a.common_market(eq,debt);execs=a.execution_map(decisions,market)
    wb,wc,wmeta=simulate_window(market,execs,policy,return_months[0],return_months[-1])

    out={
      'schema_version':1,'status':'complete','policy_id':policy['id'],
      'role':'Crash-insurance pricing disclosure. This is not evidence of timing alpha and cannot promote or change the live rule.',
      'implementation':'First shared trading close on/after each calendar decision; 10 bps per 100% one-way turnover; 20bp equity and 15bp debt annual expense assumptions; initial acquisition cost-free, matching the frozen challenger.',
      'same_63_calendar_return_months':{**wmeta,**tradeoff(wb,wc)},
      'longest_exact_shared_history':long_history_from_frozen_summary(),
      'source_metadata_for_63_month_recompute':{'equity':eqmeta,'debt':debtmeta},
      'limitations':[
        'The baseline is the legacy fixed-reference valuation-core screen, not a historical reconstruction of the complete V3.11 macro/earnings stack.',
        'The 63-month insurance window matches the calendar return months of the strict timing audit, but the trend study executes on first shared trading closes and therefore is not numerically identical to the month-end return convention in retrospective_core.py.',
        'The longest-history row is copied from the previously source-corrected green-CI trend summary rather than silently recomputed under a different endpoint snapshot.',
        'Pre-current-methodology valuation history is useful for crash stress only and is not directly comparable fair-value evidence.',
        'Taxes are excluded; the debt sleeve is the long-duration NIFTY 10 YR BENCHMARK G-SEC index.'
      ],
      'live_model_changed':False
    }
    OUT.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'same63':{'cagr_premium_pp':out['same_63_calendar_return_months']['cagr_premium_paid_pp_per_year'],'max_dd_avoided_pp':out['same_63_calendar_return_months']['max_daily_drawdown_avoided_pp']},'longest':{'cagr_premium_pp':out['longest_exact_shared_history']['cagr_premium_paid_pp_per_year'],'max_dd_avoided_pp':out['longest_exact_shared_history']['max_daily_drawdown_avoided_pp']}},separators=(',',':')))


if __name__=='__main__':main()
