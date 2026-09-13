#!/usr/bin/env python3
"""Companion audit for timing-benchmark realism and observed effect size.

This file is descriptive research only. It does not change the live allocator.
It compares the legacy valuation timing path with three nulls:
1) the existing ex-post full-sample mean-equity static comparator;
2) a pre-declared 60/40 policy comparator; and
3) an investable expanding-mean comparator using only target weights known by
   each decision date (including the current decision, before that month's
   return is earned).
"""
from __future__ import annotations

from pathlib import Path
import json, math
import numpy as np
import pandas as pd
import retrospective_core as r
import robust_evaluation as re

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'benchmark_audit.json'


def max_drawdown_pct(rets):
    a=np.asarray(rets,float)
    wealth=np.concatenate(([1.0],np.cumprod(1+a)))
    peak=np.maximum.accumulate(wealth)
    dd=wealth/peak-1
    return 100*float(np.min(dd))


def describe_comparator(name,weights,dyn,eq,db,available_ex_ante,note):
    w=pd.Series(np.asarray(weights,float),index=eq.index,dtype=float)
    net,turn=re.net_with_weights(w,eq,db)
    resid=pd.Series(dyn-net,index=eq.index,dtype=float)
    dyn_c=100*float(re.cagr(dyn));cmp_c=100*float(re.cagr(net))
    dyn_dd=max_drawdown_pct(dyn);cmp_dd=max_drawdown_pct(net)
    return {
      'name':name,'available_ex_ante':bool(available_ex_ante),'note':note,
      'comparator_mean_equity_pct':100*float(w.mean()),
      'comparator_cagr_pct':cmp_c,'comparator_max_drawdown_pct':cmp_dd,
      'dynamic_cagr_pct':dyn_c,'dynamic_max_drawdown_pct':dyn_dd,
      'dynamic_minus_comparator_cagr_pp':dyn_c-cmp_c,
      'dynamic_additional_drawdown_pp':abs(dyn_dd)-abs(cmp_dd),
      'timing_residual_monthly_sharpe':re.monthly_sharpe(resid),
      'timing_residual_t_stat_naive':re.t_stat(resid),
      'timing_residual_effective_sample':re.effective_sample_size(resid),
      'comparator_realised_turnover_x':float(np.sum(turn)),
    }


def observed_effect_horizon(timing_residual):
    resid=np.asarray(timing_residual,float);n=len(resid);t=re.t_stat(resid)
    ess=re.effective_sample_size(resid);eff=float(ess['effective_n']);ratio=eff/n if n else None
    if t is None or abs(t)<1e-12 or not ratio:
        return {'status':'unavailable'}
    raw_months=n*(2.0/abs(float(t)))**2
    adjusted_months=raw_months/ratio
    return {
      'status':'heuristic_only','observed_naive_t_stat':float(t),'observations':int(n),
      'target_absolute_t_stat':2.0,'raw_months_if_iid_effect_persisted':float(raw_months),
      'raw_years_if_iid_effect_persisted':float(raw_months/12),
      'observed_effective_sample_ratio':float(ratio),
      'serial_dependence_adjusted_months_if_same_efficiency_persisted':float(adjusted_months),
      'serial_dependence_adjusted_years_if_same_efficiency_persisted':float(adjusted_months/12),
      'interpretation':'Do not read these horizons literally. They show that the observed effect is far too small to justify a claim that merely waiting longer will validate it. Prospective evidence is useful for detecting a materially larger edge if one emerges and documenting its absence otherwise.',
      'warning':'This scaling assumes the observed effect, variance and serial-dependence structure remain stationary; that assumption is not credible over century-scale horizons.'
    }


def comparator_beta_signature(comparisons,dynamic_mean_equity_pct):
    """Three-point descriptive regression; not an inferential timing test.

    Centering the x-axis on the dynamic strategy's own mean equity makes the
    intercept directly readable as the fitted excess CAGR at equal beta.
    """
    keys=['expanding_mean_investable','ex_post_realised_mean_static','fixed_60_40_policy']
    pts=sorted([
      (float(comparisons[k]['comparator_mean_equity_pct']),float(comparisons[k]['dynamic_minus_comparator_cagr_pp']),k)
      for k in keys
    ])
    x=np.asarray([p[0]-dynamic_mean_equity_pct for p in pts],float)
    y=np.asarray([p[1] for p in pts],float)
    slope,intercept=np.polyfit(x,y,1)
    pred=intercept+slope*x
    ss_res=float(np.sum((y-pred)**2));ss_tot=float(np.sum((y-y.mean())**2))
    r2=1-ss_res/ss_tot if ss_tot>0 else None
    zero_cross=(dynamic_mean_equity_pct-intercept/slope) if abs(slope)>1e-12 else None
    monotone=all(pts[i+1][1]<=pts[i][1]+1e-12 for i in range(len(pts)-1))
    return {
      'status':'descriptive_three_point_geometry_only',
      'dynamic_mean_equity_pct':float(dynamic_mean_equity_pct),
      'points':[{'comparator':k,'equity_pct':w,'dynamic_excess_cagr_pp':e} for w,e,k in pts],
      'monotone_decreasing_excess_cagr_with_comparator_equity':bool(monotone),
      'slope_pp_excess_cagr_per_1pp_comparator_equity':float(slope),
      'fitted_excess_cagr_at_dynamic_mean_equity_pp':float(intercept),
      'fitted_zero_cross_equity_pct':float(zero_cross) if zero_cross is not None else None,
      'r_squared':float(r2) if r2 is not None else None,
      'interpretation':'Across these three comparator weights, excess CAGR falls as comparator equity rises and is near zero around the dynamic strategy\'s own mean exposure. That is the geometry expected when most return differences are equity beta and residual timing content is small. With only three dependent portfolio constructions this is descriptive, not an independent statistical test.'
    }


def main():
    retro=json.loads((ROOT/'data'/'retrospective.json').read_text(encoding='utf-8'))
    panel=re.panel_from_retrospective(retro)
    frame,_,dyn,_=r.strategy_returns(panel,r.LIVE_K,r.LIVE_ZC)
    eq=frame['eq'].astype(float);db=frame['db'].astype(float);w=frame['w'].astype(float)

    ex_post=np.full(len(w),float(w.mean()))
    fixed60=np.full(len(w),.60)
    # The decision weight w_t is known before the return assigned to row t is earned.
    # Therefore the expanding mean through w_t is implementable at that decision time.
    expanding=w.expanding(min_periods=1).mean().to_numpy(float)

    comparisons={
      'ex_post_realised_mean_static':describe_comparator(
        'Ex-post realised-mean static',ex_post,dyn,eq,db,False,
        'Uses the full sample realised mean equity weight. Useful for beta removal but unavailable to an investor at sample start.'),
      'fixed_60_40_policy':describe_comparator(
        'Fixed 60/40 policy',fixed60,dyn,eq,db,True,
        'Pre-declared policy null fixed at 60% equity for the entire return window.'),
      'expanding_mean_investable':describe_comparator(
        'Expanding-mean investable policy',expanding,dyn,eq,db,True,
        'At each decision, target equity equals the mean of valuation targets observed through that decision; no future target weights are used.'),
    }

    base=comparisons['ex_post_realised_mean_static']
    sentence=f"Over the tested window, moving equity exposure added {base['dynamic_minus_comparator_cagr_pp']:.2f} pp/year of return and {base['dynamic_additional_drawdown_pp']:.1f} pp of additional drawdown."
    fx=comparisons['fixed_60_40_policy']
    investable_sentence=f"Against a pre-declared 60/40 policy over the same window, the dynamic model changed CAGR by {fx['dynamic_minus_comparator_cagr_pp']:+.2f} pp/year and maximum drawdown by {fx['dynamic_additional_drawdown_pp']:+.2f} pp."
    static_net,_=re.net_with_weights(ex_post,eq,db)
    horizon=observed_effect_horizon(pd.Series(dyn-static_net,index=frame.index,dtype=float))
    signature=comparator_beta_signature(comparisons,100*float(w.mean()))

    out={
      'schema_version':2,'status':'complete','months':int(len(frame)),
      'scope':'Legacy fixed-reference valuation-core timing window; not a certified full-stack V3.11 backtest.',
      'observed_tradeoff_sentence':sentence,
      'decision_relevant_60_40_sentence':investable_sentence,
      'comparators':comparisons,
      'comparator_beta_signature':signature,
      'observed_effect_scale':horizon,
      'governance':'The ex-post mean comparator remains valid for beta-removal diagnostics but is explicitly not investable. Promotion claims should also survive investable nulls; no result here changes live parameters automatically.'
    }
    OUT.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({
      'sentence':sentence,
      'investable_sentence':investable_sentence,
      'beta_signature':signature,
      'fixed60_edge_pp':comparisons['fixed_60_40_policy']['dynamic_minus_comparator_cagr_pp'],
      'expanding_edge_pp':comparisons['expanding_mean_investable']['dynamic_minus_comparator_cagr_pp'],
      'expanding_additional_drawdown_pp':comparisons['expanding_mean_investable']['dynamic_additional_drawdown_pp'],
      'iid_years_to_t2':horizon.get('raw_years_if_iid_effect_persisted'),
      'serial_adjusted_years_to_t2':horizon.get('serial_dependence_adjusted_years_if_same_efficiency_persisted')
    },separators=(',',':')))


if __name__=='__main__':main()
