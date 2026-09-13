#!/usr/bin/env python3
"""Source-corrected runner for the frozen trend challenger.

NSE Indices publishes fixed-income index levels on a total-return basis except
for the separately named Clean Price index. This wrapper preserves every
signal/simulation rule in trend_challenger_backtest.py and replaces only the
debt data loader with the historical close of the exact frozen index.
"""
from __future__ import annotations
from datetime import date
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


a.debt_tri_daily=debt_tri_daily

if __name__=='__main__':a.main()
