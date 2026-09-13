from pathlib import Path
import json,sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import trend_challenger_backtest as t


def test_frozen_policy_rule_has_not_drifted():
    p=t.load_policy()
    assert p['id']=='trend-sma10-minus20-v1'
    assert p['lookback_months']==10
    assert p['risk_off_adjustment_pp']==20
    assert p['live_allocation_effect']=='none'


def test_challenger_reduces_exactly_20pp_with_zero_floor():
    assert t.challenger_target(.80,True,20)==.60
    assert t.challenger_target(.15,True,20)==0.0
    assert t.challenger_target(1.00,True,20)==.80
    assert t.challenger_target(.80,False,20)==.80


def test_sma_uses_previous_completed_month_and_equality_is_risk_on():
    # Jan-Oct closes are 1..10. Nov-1 decision sees Jan-Oct only: last=10,
    # mean=5.5 => risk-on. Dec-1 sees Feb-Nov after Nov close=1: last=1,
    # mean=(2+...+10+1)/10=5.5 => risk-off.
    idx=pd.date_range('2020-01-31',periods=11,freq='ME')
    s=pd.Series(list(range(1,11))+[1.0],index=idx,dtype=float)
    d=t.trend_decisions(pd.to_datetime(['2020-11-01','2020-12-01']),s,10)
    assert bool(d.loc[pd.Timestamp('2020-11-01'),'risk_off']) is False
    assert bool(d.loc[pd.Timestamp('2020-12-01'),'risk_off']) is True
    # Equality is explicitly not risk-off.
    s2=pd.Series([5.0]*10,index=pd.date_range('2021-01-31',periods=10,freq='ME'))
    e=t.trend_decisions(pd.to_datetime(['2021-11-01']),s2,10)
    assert bool(e.iloc[0].risk_off) is False


def test_missing_calendar_month_fails_signal_instead_of_shortening_sma():
    idx=pd.to_datetime(['2020-01-31','2020-02-29','2020-03-31','2020-04-30','2020-05-31','2020-06-30','2020-07-31','2020-08-31','2020-10-31','2020-11-30'])
    s=pd.Series(range(10),index=idx,dtype=float)
    d=t.trend_decisions(pd.to_datetime(['2020-12-01']),s,10)
    assert pd.isna(d.iloc[0].risk_off)


def synthetic_market():
    idx=pd.bdate_range('2020-01-01','2020-04-30')
    # Equity rises then falls; debt stable.
    eq=np.linspace(100,130,len(idx));eq[len(idx)//2:]=np.linspace(eq[len(idx)//2],90,len(idx)-len(idx)//2)
    debt=np.linspace(100,101,len(idx))
    return pd.DataFrame({'equity':eq,'debt':debt},index=idx)


def synthetic_execs():
    idx=pd.to_datetime(['2020-01-01','2020-02-03','2020-03-02','2020-04-01'])
    return pd.DataFrame({'baseline_target':[.8,.8,.8,.8],'challenger_target':[.8,.6,.6,.8],'risk_off':[False,True,True,False]},index=idx)


def test_rebalance_band_uses_drifted_actual_weight():
    m=synthetic_market();x=synthetic_execs()
    _,f0=t.simulate_daily(m,x,'challenger_target',band_pp=0,cost_rate=0,eq_expense=0,debt_expense=0)
    _,f5=t.simulate_daily(m,x,'challenger_target',band_pp=5,cost_rate=0,eq_expense=0,debt_expense=0)
    assert f5['rebalances']<=f0['rebalances']


def test_costs_reduce_wealth_and_are_one_way():
    m=synthetic_market();x=synthetic_execs()
    a,fa=t.simulate_daily(m,x,'challenger_target',band_pp=0,cost_rate=0,eq_expense=0,debt_expense=0)
    b,fb=t.simulate_daily(m,x,'challenger_target',band_pp=0,cost_rate=.005,eq_expense=0,debt_expense=0)
    assert b.value.iloc[-1]<a.value.iloc[-1]
    assert fb['cost_paid']>0
    assert fb['turnover_value']>0


def test_negative_constituent_or_market_returns_do_not_break_daily_metrics():
    m=synthetic_market();x=synthetic_execs()
    q,f=t.simulate_daily(m,x,'challenger_target',band_pp=0,cost_rate=.001,eq_expense=.002,debt_expense=.0015)
    z=t.metrics(q,f)
    assert z['max_daily_drawdown_pct']<=0
    assert np.isfinite(z['daily_ulcer_index_pct'])


def test_no_live_files_written_by_research_script():
    text=(ROOT/'scripts'/'trend_challenger_backtest.py').read_text()
    for forbidden in ("ROOT/'model.js'","ROOT/'data'/'latest.json'","archive_evidence.py"):
        assert forbidden not in text
