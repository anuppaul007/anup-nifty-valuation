#!/usr/bin/env python3
"""Strict integrated anchor v3: taxonomy-complete 2026 runner.

Extends v2 with pre-result taxonomy rules established from NSE's standardized
Mar/Jun-2026 filings:
- annual banking book value = Capital + ReservesAndSurplus in OneI;
- life-insurance direct ShareholdersFunds is preferred when reported;
- zero placeholder profit tags do not override a non-zero disclosed PAT fact.
All PIT, 50/50 coverage and predeclared tolerance rules remain unchanged.
"""
from __future__ import annotations
import math
import current_definition_integrated_anchor_v2 as h

a=h.a


def profit_from(fs):
    zero_candidate=None
    for name in a.PROFIT_NAMES:
        f=a.pick(fs,[name],['OneD'])
        if f is None:continue
        if math.isfinite(float(f['value'])) and abs(float(f['value']))>0:
            return f
        if zero_candidate is None and math.isfinite(float(f['value'])):
            zero_candidate=f
    if zero_candidate is not None:return zero_candidate
    raise ValueError('profit_fact_missing')

a.profit_from=profit_from


def networth_from(fs):
    # Direct shareholders' funds, especially life-insurance taxonomy.
    f=a.pick(fs,['ShareholdersFunds'],['OneI'])
    if f is not None and math.isfinite(float(f['value'])):
        return f,'direct_shareholders_funds'
    # Standard IndAS direct equity/net-worth facts.
    f=a.pick(fs,a.EQUITY_NAMES,['OneI'])
    if f is not None and math.isfinite(float(f['value'])):
        return f,'direct'
    # Banking integrated-filing balance sheet: equity capital and reserves are
    # explicit OneI instant facts. This mirrors NIFTY's book-value description
    # of equity capital plus reserves/surplus from the annual financial report.
    bank_cap=a.pick(fs,['Capital'],['OneI'])
    bank_res=a.pick(fs,['ReservesAndSurplus'],['OneI'])
    if bank_cap and bank_res and all(math.isfinite(float(x['value'])) for x in (bank_cap,bank_res)):
        return {'name':'Capital+ReservesAndSurplus','context':'OneI','value':bank_cap['value']+bank_res['value']},'bank_capital_plus_reserves'
    # Standard separate equity-capital + other-equity format.
    cap=a.pick(fs,a.CAP_NAMES,['OneI']);other=a.pick(fs,a.OTHER_EQUITY_NAMES,['OneI'])
    if cap and other and cap['value']>0 and all(math.isfinite(float(x['value'])) for x in (cap,other)):
        return {'name':cap['name']+'+'+other['name'],'context':'OneI','value':cap['value']+other['value']},'capital_plus_other_equity'
    # Conservative insurance fallback only if direct ShareholdersFunds is absent.
    icap=a.pick(fs,['PaidUpEquityShareCapital'],['OneI'])
    reserve=a.pick(fs,a.INSURANCE_RESERVE_NAMES,['OneI','OneD','FourD'])
    fv=a.pick(fs,a.INSURANCE_FV_NAMES,['OneI','OneD','FourD'])
    if icap and reserve and icap['value']>0 and math.isfinite(float(reserve['value'])):
        value=icap['value']+reserve['value']+(fv['value'] if fv and math.isfinite(float(fv['value'])) else 0.0)
        names=[icap['name'],reserve['name']]+([fv['name']] if fv else [])
        return {'name':'+'.join(names),'context':'insurance_shareholders_fund','value':value},'insurance_shareholders_fund_fallback'
    raise ValueError('networth_fact_missing')

h.networth_from=networth_from
a.networth_from=networth_from

if __name__=='__main__':
    a.main()
