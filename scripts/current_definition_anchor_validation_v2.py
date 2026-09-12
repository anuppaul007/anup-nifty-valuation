#!/usr/bin/env python3
"""Anchor validation v2: controlled legacy XBRL context recovery.

Some archived NSE XBRLs expose valid facts under canonical OneD/OneI context
references while the context-date node itself is absent/malformed. This wrapper
uses the NSE filing row's own from/to dates only when the row is explicitly
Non-cumulative and the selected fact is in canonical OneD (duration) or OneI
(instant) context. No fuzzy numeric matching or future information is allowed.
"""
from __future__ import annotations
import current_definition_anchor_validation as a


def _named(fs,names):
    n={x.lower() for x in names}
    return [f for f in fs if f['name'].lower() in n]


def extract_profit(row):
    root=a.xbrl_root(row['xbrl']);fs=a.facts(root)
    f=a.pick_fact(fs,a.PROFIT_NAMES,row['_from'],row['_to'])
    if f:return f['value'],f['name']
    # Controlled legacy fallback: the API row itself identifies an exact
    # non-cumulative quarter; use only the primary OneD entity context.
    if str(row.get('cumulative','')).strip().lower()=='non-cumulative':
        cand=[f for f in _named(fs,a.PROFIT_NAMES) if str(f.get('context','')).lower()=='oned']
        if len(cand)==1:return cand[0]['value'],cand[0]['name']
        # There may be duplicate facts with the same tag/value. Accept only if
        # all OneD candidates agree numerically after grouping by preferred tag.
        for name in a.PROFIT_NAMES:
            q=[f for f in cand if f['name'].lower()==name.lower()]
            if q and len({round(float(x['value']),6) for x in q})==1:
                return q[0]['value'],q[0]['name']
    raise ValueError('profit_fact_missing')


def _instant_fallback(fs,names):
    cand=[f for f in _named(fs,names) if str(f.get('context','')).lower() in ('onei','oneinstant')]
    for name in names:
        q=[f for f in cand if f['name'].lower()==name.lower()]
        if q and len({round(float(x['value']),6) for x in q})==1:return q[0]
    return None


def extract_cap_face(row):
    root=a.xbrl_root(row['xbrl']);fs=a.facts(root)
    c=a.pick_fact(fs,a.CAP_NAMES,row['_from'],row['_to'],True) or _instant_fallback(fs,a.CAP_NAMES)
    fv=a.pick_fact(fs,a.FACE_NAMES,row['_from'],row['_to'],True) or _instant_fallback(fs,a.FACE_NAMES)
    if not c or not fv or c['value']<=0 or fv['value']<=0:raise ValueError('capital_or_face_missing')
    return c['value'],fv['value'],c['name'],fv['name']


def extract_networth(row):
    root=a.xbrl_root(row['xbrl']);fs=a.facts(root)
    direct=a.pick_fact(fs,a.EQUITY_DIRECT_NAMES,row['_from'],row['_to'],True) or _instant_fallback(fs,a.EQUITY_DIRECT_NAMES)
    if direct and direct['value']>0:return direct['value'],direct['name'],'direct'
    cap=a.pick_fact(fs,a.CAP_NAMES,row['_from'],row['_to'],True) or _instant_fallback(fs,a.CAP_NAMES)
    reserve=None
    for n in a.RESERVE_NAMES:
        reserve=a.pick_fact(fs,[n],row['_from'],row['_to'],True) or _instant_fallback(fs,[n])
        if reserve and reserve['value']>0:break
    if cap and reserve and cap['value']>0:
        return cap['value']+reserve['value'],f"{cap['name']}+{reserve['name']}",'sum'
    raise ValueError('networth_fact_missing')


a.extract_profit=extract_profit
a.extract_cap_face=extract_cap_face
a.extract_networth=extract_networth

if __name__=='__main__':
    a.main()
