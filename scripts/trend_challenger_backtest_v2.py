#!/usr/bin/env python3
"""Source-corrected runner for the frozen trend challenger.

NSE Indices publishes fixed-income index levels on a total-return basis except
for the separately named Clean Price index. This wrapper preserves every
signal/simulation rule in trend_challenger_backtest.py and replaces only the
debt data loader with the historical close of the exact frozen index.

After the no-cashflow backtest is complete, this runner removes the naive CAGR
field from SIP/withdrawal companions. CAGR computed from terminal/start wealth
is not a valid return measure when external cash flows exist; those scenarios
are assessed by terminal wealth, withdrawal shortfall and path-risk metrics.
"""
from __future__ import annotations
from datetime import date
import json
import trend_challenger_backtest as a


def debt_tri_daily():
    from jugaad_data.nse import index_raw
    exact='NIFTY 10 YR BENCHMARK G-SEC'
    s=a._parse_index_rows(index_raw(exact,a.START,date.today()))
    if len(s)<200:
        raise RuntimeError(f'Exact frozen debt total-return index unavailable: {len(s)} rows; substitution forbidden')
    return s,{
      'index':exact,
      'retrieval':'historical index close',
      'total_return_basis':'NSE Indices fixed-income convention; Clean Price is a separately named excluded index',
      'rows':len(s),'first':str(s.index.min().date()),'last':str(s.index.max().date()),'substituted':False,
    }


def clean_cashflow_metrics():
    out=json.loads(a.OUT.read_text(encoding='utf-8'))
    for scenario in ('sip','retirement_withdrawal'):
        block=out.get('cashflow_companions',{}).get(scenario,{})
        for side in ('baseline','challenger'):
            m=block.get(side)
            if not isinstance(m,dict):continue
            m.pop('cagr_pct',None)
            m['return_metric_status']='CAGR intentionally not reported because external cash flows make terminal/start CAGR invalid'
    out.setdefault('cashflow_companion_note','Terminal wealth/withdrawal shortfall are primary cash-flow outputs. Drawdown/Ulcer are path-of-account-value diagnostics and are affected by contributions/withdrawals; they are not time-weighted investment-return statistics.')
    out['historical_conclusion']='retain_as_prospective_challenger_not_promote'
    a.OUT.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8')


a.debt_tri_daily=debt_tri_daily

if __name__=='__main__':
    a.main()
    clean_cashflow_metrics()
