#!/usr/bin/env python3
"""Historical stress test for the pre-registered SMA10 trend challenger.

Research only. This script MUST NOT modify model.js, latest.json, the live
recommendation, or any existing evidence ledger. The rule is read from the
already-frozen trend_policy_v1.json and asserted before use.

Historical evidence boundary:
* baseline allocations come from data/monthly_signal_screen.json, i.e. the
  legacy fixed-reference V3.6 valuation core;
* this is not a historical test of the full modern macro/earnings model;
* historical valuation/accounting definitions are mixed as documented by the
  project's methodology audit;
* exact NIFTY 50 TRI and NIFTY 10 YR BENCHMARK G-SEC TRI are required. The
  script fails closed rather than fabricating a debt sleeve.
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from pathlib import Path
import json, math
import numpy as np
import pandas as pd
import update_data as b

ROOT=Path(__file__).resolve().parents[1]
POLICY_FILE=ROOT/'trend_policy_v1.json'
SIGNAL_FILE=ROOT/'data'/'monthly_signal_screen.json'
OUT=ROOT/'data'/'trend_challenger_backtest.json'
START=date(2000,1,1)


def finite(x):
    try:return x is not None and math.isfinite(float(x))
    except (TypeError,ValueError):return False


def load_policy():
    p=json.loads(POLICY_FILE.read_text(encoding='utf-8'))
    frozen={
      'id':'trend-sma10-minus20-v1','lookback_months':10,
      'risk_off_adjustment_pp':20,'rebalance_band_pp':0,
      'implementation_challenger_band_pp':5,
    }
    for k,v in frozen.items():
        if p.get(k)!=v:raise RuntimeError(f'Frozen trend policy drift: {k}={p.get(k)!r}, expected {v!r}')
    if p.get('live_allocation_effect')!='none':raise RuntimeError('Frozen policy is no longer research-only')
    return p


def _parse_index_rows(rows):
    pts=[]
    for x in rows or []:
        dt=b.pdate(b.pick(x,['Date','DATE','HistoricalDate','Index Date']))
        val=b.fnum(b.pick(x,['Total Returns Index','TRI','Close','CLOSE','Closing Index Value','Index Value','INDEX_VALUE','close']))
        if dt and finite(val) and float(val)>0:pts.append((pd.Timestamp(dt).normalize(),float(val)))
    if not pts:return pd.Series(dtype=float)
    return pd.DataFrame(pts,columns=['date','value']).drop_duplicates('date').set_index('date').value.sort_index()


def nifty_price_daily():
    from jugaad_data.nse import index_raw
    s=_parse_index_rows(index_raw('NIFTY 50',START,date.today()))
    if len(s)<1000:raise RuntimeError(f'Insufficient NIFTY 50 price history: {len(s)}')
    return s


def tri_daily(family,index):
    from jugaad_data.nse import index_tri_raw
    s=_parse_index_rows(index_tri_raw(family,index,START,date.today()))
    return s


def equity_tri_daily():
    s=tri_daily('NIFTY 50','NIFTY 50')
    if len(s)<1000:raise RuntimeError(f'Insufficient NIFTY 50 TRI history: {len(s)}')
    return s,{'index':'NIFTY 50 TRI','family':'NIFTY 50','rows':len(s),'first':str(s.index.min().date()),'last':str(s.index.max().date())}


def debt_tri_daily():
    exact='NIFTY 10 YR BENCHMARK G-SEC'
    candidates=[exact,'NIFTY FIXED INCOME','NIFTY FIXED INCOME INDICES']
    errors=[]
    for family in candidates:
        try:
            s=tri_daily(family,exact)
            if len(s)>=200:
                return s,{'index':exact,'family':family,'rows':len(s),'first':str(s.index.min().date()),'last':str(s.index.max().date()),'substituted':False}
            errors.append(f'{family}: only {len(s)} rows')
        except Exception as e:errors.append(f'{family}: {type(e).__name__}: {e}')
    raise RuntimeError('Exact frozen debt TRI unavailable; substitution forbidden. '+' | '.join(errors))


def load_baseline_targets():
    raw=json.loads(SIGNAL_FILE.read_text(encoding='utf-8'))
    rows=[]
    for r in raw.get('records',[]):
        dt=pd.Timestamp(r['signal_date']).normalize();eq=r.get('core_equity')
        if finite(eq):rows.append((dt,float(eq)/100.0,r.get('methodology_era')))
    if not rows:raise RuntimeError('No monthly valuation-core targets')
    q=pd.DataFrame(rows,columns=['signal_date','baseline_target','methodology_era']).drop_duplicates('signal_date').set_index('signal_date').sort_index()
    return q,{'scope':raw.get('scope'),'decision_rule':raw.get('decision_rule'),'yield_rule':raw.get('yield_rule'),'generated_at':raw.get('generated_at')}


def completed_month_closes(price):
    return price.groupby(price.index.to_period('M')).last().sort_index()


def trend_decisions(signal_dates,price,lookback=10):
    """Return no-lookahead SMA10 state for calendar decision dates.

    Each signal uses exactly the 10 calendar months ending immediately before
    the decision month. A missing completed calendar month makes that decision
    ineligible rather than silently shortening the moving average.
    """
    closes=completed_month_closes(price);out=[]
    for dt in pd.DatetimeIndex(signal_dates):
        mo=dt.to_period('M');months=pd.period_range(mo-lookback,mo-1,freq='M')
        if any(m not in closes.index for m in months):
            out.append((dt,np.nan,np.nan,None));continue
        vals=closes.loc[months].astype(float);last=float(vals.iloc[-1]);sma=float(vals.mean())
        out.append((dt,last,sma,bool(last<sma)))
    return pd.DataFrame(out,columns=['signal_date','prior_month_close','sma10','risk_off']).set_index('signal_date')


def challenger_target(baseline,risk_off,adjust_pp=20):
    b=float(baseline)
    return max(0.0,b-float(adjust_pp)/100.0) if bool(risk_off) else b


def build_decisions(policy,price):
    base,meta=load_baseline_targets();tr=trend_decisions(base.index,price,int(policy['lookback_months']))
    q=base.join(tr,how='left');q=q[q.risk_off.notna()].copy()
    q['risk_off']=q.risk_off.astype(bool)
    q['challenger_target']=[challenger_target(b,r,policy['risk_off_adjustment_pp']) for b,r in zip(q.baseline_target,q.risk_off)]
    q['adjustment_pp']=100*(q.challenger_target-q.baseline_target)
    return q,meta


def common_market(eq,debt):
    idx=eq.index.intersection(debt.index).sort_values()
    if len(idx)<200:raise RuntimeError('Insufficient exact shared TRI history')
    return pd.DataFrame({'equity':eq.reindex(idx),'debt':debt.reindex(idx)}).dropna()


def execution_map(decisions,market):
    rows=[];idx=market.index
    for dt,r in decisions.iterrows():
        pos=idx.searchsorted(dt,side='left')
        if pos>=len(idx):continue
        ex=idx[pos]
        rows.append({'signal_date':dt,'execution_date':ex,'baseline_target':float(r.baseline_target),'challenger_target':float(r.challenger_target),'risk_off':bool(r.risk_off),'prior_month_close':float(r.prior_month_close),'sma10':float(r.sma10),'methodology_era':r.methodology_era})
    if not rows:raise RuntimeError('No executable trend decisions')
    q=pd.DataFrame(rows).drop_duplicates('execution_date',keep='last').set_index('execution_date').sort_index()
    # Restrict to decisions whose execution lies inside exact shared market data.
    return q[(q.index>=market.index.min())&(q.index<=market.index.max())]


def _expense_growth(annual,days):
    return (1.0-float(annual))**(float(days)/365.2425)


def simulate_daily(market,execs,target_col,band_pp,cost_rate,eq_expense,debt_expense,
                   initial=1_000_000.0,monthly_contribution=0.0,
                   annual_withdrawal0=0.0,withdrawal_inflation=0.0):
    start=execs.index.min();end=market.index.max();m=market.loc[start:end].copy()
    execs=execs.loc[(execs.index>=start)&(execs.index<=end)]
    if start not in execs.index:raise RuntimeError('Simulation must start on an execution date')
    e=d=None;prev=None;turnover_value=0.0;cost_paid=0.0;contrib=0.0;withdrawn=0.0;shortfall=0.0;records=[];rebals=0
    exec_counter=0
    for dt,row in m.iterrows():
        if prev is not None:
            days=max(1,(dt-prev).days)
            e*=float(row.equity/m.loc[prev,'equity'])*_expense_growth(eq_expense,days)
            d*=float(row.debt/m.loc[prev,'debt'])*_expense_growth(debt_expense,days)
        if dt in execs.index:
            x=execs.loc[dt];target=float(x[target_col]);v=float(initial) if e is None else e+d
            if e is None:
                # Initial acquisition is explicitly cost-free under the policy.
                e=v*target;d=v*(1-target)
            else:
                # External flow occurs at execution close before rebalancing.
                if monthly_contribution:
                    add=float(monthly_contribution);w=e/v if v>0 else target;e+=add*w;d+=add*(1-w);contrib+=add;v=e+d
                if annual_withdrawal0:
                    months=exec_counter;want=float(annual_withdrawal0)/12.0*(1+float(withdrawal_inflation))**(months/12.0)
                    take=min(v,want);gap=max(0.0,want-v);shortfall+=gap
                    if v>0:
                        w=e/v;e-=take*w;d-=take*(1-w)
                    withdrawn+=take;v=e+d
                current=e/v if v>0 else target
                if abs(target-current)*100.0>float(band_pp):
                    one_way=abs(target-current)*v;fee=one_way*float(cost_rate);v_after=max(0.0,v-fee)
                    turnover_value+=one_way;cost_paid+=fee;rebals+=1
                    e=v_after*target;d=v_after*(1-target)
            exec_counter+=1
        if e is not None:
            v=e+d;records.append({'date':dt,'value':v,'equity_value':e,'debt_value':d,'equity_weight':(e/v if v>0 else np.nan)})
        prev=dt
    df=pd.DataFrame(records).set_index('date')
    return df,{'turnover_value':turnover_value,'cost_paid':cost_paid,'contributions':contrib,'withdrawn':withdrawn,'withdrawal_shortfall':shortfall,'rebalances':rebals}


def drawdown_series(v):
    return v/v.cummax()-1.0


def longest_underwater(dd):
    best=cur=0
    for x in (dd<0).to_numpy():
        if x:cur+=1;best=max(best,cur)
        else:cur=0
    return int(best)


def metrics(df,flows=None):
    v=df.value.astype(float);dd=drawdown_series(v);years=(v.index[-1]-v.index[0]).days/365.2425
    cagr=(float(v.iloc[-1]/v.iloc[0])**(1/years)-1) if years>0 and v.iloc[0]>0 else np.nan
    month=v.groupby(v.index.to_period('M')).last();mr=month.pct_change().dropna();n=max(1,int(math.ceil(len(mr)*0.05)));es=float(mr.nsmallest(n).mean()) if len(mr) else np.nan
    ulcer=float(np.sqrt(np.mean(np.square(np.minimum(dd.to_numpy(),0.0)))))
    out={'start':str(v.index[0].date()),'end':str(v.index[-1].date()),'days':int(len(v)),'ending_value':float(v.iloc[-1]),'cagr_pct':100*cagr,'max_daily_drawdown_pct':100*float(dd.min()),'monthly_expected_shortfall_95_pct':100*es,'daily_ulcer_index_pct':100*ulcer,'longest_underwater_trading_days':longest_underwater(dd),'average_equity_exposure_pct':100*float(df.equity_weight.mean())}
    if flows:
        out.update({'one_way_turnover_multiple_of_initial':float(flows['turnover_value']/max(float(v.iloc[0]),1e-12)),'cost_paid':float(flows['cost_paid']),'contributions':float(flows['contributions']),'withdrawn':float(flows['withdrawn']),'withdrawal_shortfall':float(flows['withdrawal_shortfall']),'rebalances':int(flows['rebalances'])})
    return out


def stress_metrics(df,windows):
    out={}
    for name,(a,z) in windows.items():
        q=df.loc[pd.Timestamp(a):pd.Timestamp(z)]
        if len(q)<2:out[name]={'status':'outside_sample'};continue
        dd=drawdown_series(q.value)
        out[name]={'start':str(q.index[0].date()),'end':str(q.index[-1].date()),'max_daily_drawdown_pct':100*float(dd.min()),'end_to_start_return_pct':100*(float(q.value.iloc[-1]/q.value.iloc[0])-1)}
    return out


def price_benchmark(series,start,end,initial=1_000_000.0):
    s=series.loc[start:end];v=initial*s/s.iloc[0]
    # Benchmark has 100% equity exposure by definition.
    return pd.DataFrame({'value':v,'equity_value':v,'debt_value':0.0,'equity_weight':1.0},index=s.index)


def run_variant(market,execs,policy,band,cost):
    kwargs=dict(band_pp=band,cost_rate=cost,eq_expense=policy['annual_expense_assumptions']['equity'],debt_expense=policy['annual_expense_assumptions']['debt'])
    b,bf=simulate_daily(market,execs,'baseline_target',**kwargs)
    c,cf=simulate_daily(market,execs,'challenger_target',**kwargs)
    return b,bf,c,cf


def main():
    policy=load_policy();price=nifty_price_daily();eq,eqmeta=equity_tri_daily();debt,debtmeta=debt_tri_daily();decisions,signalmeta=build_decisions(policy,price);market=common_market(eq,debt);execs=execution_map(decisions,market)
    if len(execs)<24:raise RuntimeError(f'Only {len(execs)} executable monthly decisions on exact shared TRI history')
    variants={};reference=None
    for band in [float(policy['rebalance_band_pp']),float(policy['implementation_challenger_band_pp'])]:
        for cost in [float(x) for x in policy['turnover_costs']]:
            key=f'band{band:g}pp_cost{cost*10000:g}bps';bd,bf,ch,cf=run_variant(market,execs,policy,band,cost)
            result={'baseline':metrics(bd,bf),'challenger':metrics(ch,cf),'delta':{'max_drawdown_improvement_pp':metrics(ch,cf)['max_daily_drawdown_pct']-metrics(bd,bf)['max_daily_drawdown_pct'],'cagr_delta_pp':metrics(ch,cf)['cagr_pct']-metrics(bd,bf)['cagr_pct']},'stress':{'baseline':stress_metrics(bd,policy['stress_windows']),'challenger':stress_metrics(ch,policy['stress_windows'])}}
            variants[key]=result
            if band==0 and abs(cost-0.001)<1e-12:reference=(bd,bf,ch,cf,result)
    if reference is None:raise RuntimeError('Reference variant missing')
    bd,bf,ch,cf,ref=reference
    # Exposure-matched diagnostic: fixed monthly target equal to challenger realized daily average exposure.
    avg=float(ch.equity_weight.mean());static_exec=execs.copy();static_exec['static_target']=avg
    st,sf=simulate_daily(market,static_exec,'static_target',band_pp=0,cost_rate=.001,eq_expense=policy['annual_expense_assumptions']['equity'],debt_expense=policy['annual_expense_assumptions']['debt'])
    # 60/40 monthly-rebalanced benchmark on same sleeves and implementation assumptions.
    sixty=execs.copy();sixty['static_target']=.60
    sx,sxf=simulate_daily(market,sixty,'static_target',band_pp=0,cost_rate=.001,eq_expense=policy['annual_expense_assumptions']['equity'],debt_expense=policy['annual_expense_assumptions']['debt'])
    nifty=price_benchmark(eq,bd.index[0],bd.index[-1])
    # Cash-flow companions for reference baseline/challenger.
    common_kwargs=dict(band_pp=0,cost_rate=.001,eq_expense=policy['annual_expense_assumptions']['equity'],debt_expense=policy['annual_expense_assumptions']['debt'])
    sip_b,sip_bf=simulate_daily(market,execs,'baseline_target',monthly_contribution=policy['cashflow_assumptions']['sip_monthly'],**common_kwargs)
    sip_c,sip_cf=simulate_daily(market,execs,'challenger_target',monthly_contribution=policy['cashflow_assumptions']['sip_monthly'],**common_kwargs)
    annual_w=policy['cashflow_assumptions']['retirement_initial']*policy['cashflow_assumptions']['retirement_initial_annual_withdrawal_rate']
    ret_b,ret_bf=simulate_daily(market,execs,'baseline_target',initial=policy['cashflow_assumptions']['retirement_initial'],annual_withdrawal0=annual_w,withdrawal_inflation=policy['cashflow_assumptions']['withdrawal_inflation'],**common_kwargs)
    ret_c,ret_cf=simulate_daily(market,execs,'challenger_target',initial=policy['cashflow_assumptions']['retirement_initial'],annual_withdrawal0=annual_w,withdrawal_inflation=policy['cashflow_assumptions']['withdrawal_inflation'],**common_kwargs)
    risk_months=int(execs.risk_off.sum());total=int(len(execs))
    exposure_matched=metrics(st,sf);nifty_m=metrics(nifty);sixty_m=metrics(sx,sxf)
    # Historical result is descriptive only. Frozen prospective promotion gate remains controlling.
    historical_gate={
      'drawdown_requirement_met':(ref['delta']['max_drawdown_improvement_pp']>=float(policy['promotion_requirements']['drawdown_improvement_pp'])),
      'cagr_sacrifice_requirement_met':(ref['delta']['cagr_delta_pp']>=-float(policy['promotion_requirements']['maximum_cagr_sacrifice_pp'])),
      'beats_exposure_matched_drawdown':ref['challenger']['max_daily_drawdown_pct']>exposure_matched['max_daily_drawdown_pct'],
      'historical_result_can_promote_live':False,
    }
    out={
      'schema_version':1,'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
      'research_only':True,'frozen_policy':policy,'historical_scope':policy['historical_scope'],
      'source_metadata':{'signal':signalmeta,'equity_tri':eqmeta,'debt_tri':debtmeta,'nifty_price':{'rows':len(price),'first':str(price.index.min().date()),'last':str(price.index.max().date())}},
      'sample':{'first_execution':str(execs.index.min().date()),'last_execution':str(execs.index.max().date()),'monthly_decisions':total,'risk_off_months':risk_months,'risk_off_pct':100*risk_months/total,'shared_daily_rows':int(len(market.loc[execs.index.min():]))},
      'reference_variant':'band0pp_cost10bps','variants':variants,
      'benchmarks':{'nifty50_tri_buy_hold':nifty_m,'sixty_forty_monthly':sixty_m,'exposure_matched_static_monthly':exposure_matched,'exposure_matched_target_pct':100*avg},
      'cashflow_companions':{
        'sip':{'baseline':metrics(sip_b,sip_bf),'challenger':metrics(sip_c,sip_cf)},
        'retirement_withdrawal':{'baseline':metrics(ret_b,ret_bf),'challenger':metrics(ret_c,ret_cf)},
      },
      'historical_review_gate':historical_gate,
      'limitations':['Historical baseline is the legacy V3.6 valuation-core screen, not the full modern model.','Pre-2021 index valuation methodology differs from the current accounting definition.','Taxes are not modelled in v1.','The debt sleeve is a long-duration NIFTY 10 YR BENCHMARK G-SEC TRI sensitivity, not a liquid-fund substitute.','Historical results cannot authorize live promotion; prospective evidence requirements remain frozen.'],
      'decision_rows':[{**{'execution_date':str(dt.date())},**{k:(bool(v) if isinstance(v,(bool,np.bool_)) else float(v) if isinstance(v,(float,np.floating)) else str(v)) for k,v in row.items()}} for dt,row in execs.iterrows()],
      'live_model_changed':False,'live_allocation_changed':False,'existing_evidence_ledger_changed':False,'live_change_authorized':False,
    }
    OUT.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'sample':out['sample'],'reference':ref,'benchmarks':out['benchmarks'],'historical_review_gate':historical_gate},indent=2))

if __name__=='__main__':main()
