"""Separate valuation-regime diagnostic for Anup Nifty Valuation V3.6.

NSE Indices changed index P/E from standalone to consolidated trailing earnings
and changed dividend-yield treatment effective 31 March 2021.  Pre-change P/E
and dividend-yield observations are therefore not silently mixed with the
current methodology.  P/B changed on 29 September 2023. This module uses only the common post-change era and is
*diagnostic only*: it does not alter the live allocation rule.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd

METHODOLOGY_START='2023-09'
MIN_MONTHS=36


def finite(x):
    try:return x is not None and math.isfinite(float(x))
    except (TypeError,ValueError):return False

def _pct(values,current,cheap_when_low=True):
    a=np.asarray([float(x) for x in values if finite(x)],dtype=float)
    if not len(a) or not finite(current):return None
    # Fraction of the historical regime that is more expensive than/currently
    # cheaper than today's reading. 100 = today's valuation is cheapest.
    return float(100*np.mean(a>=float(current))) if cheap_when_low else float(100*np.mean(a<=float(current)))

def _stats(values):
    a=np.asarray([float(x) for x in values if finite(x)],dtype=float)
    if not len(a):return None
    med=float(np.median(a));q25=float(np.quantile(a,.25));q75=float(np.quantile(a,.75));mad=float(np.median(np.abs(a-med)))
    return {'median':med,'q25':q25,'q75':q75,'mad':mad,'robust_sigma':1.4826*mad,'min':float(np.min(a)),'max':float(np.max(a)),'observations':int(len(a))}

def build(history,latest):
    rows=[];current_month=str(latest.get('date',''))[:7]
    for row in history or []:
        if not isinstance(row,(list,tuple)) or len(row)<4:continue
        month,pe,pb,dy=row[:4]
        if str(month)<METHODOLOGY_START or str(month)>=current_month:continue
        if finite(pe) and finite(pb) and finite(dy):rows.append((str(month),float(pe),float(pb),float(dy)))
    if not rows:
        return {'status':'unavailable','months':0,'methodology_start':METHODOLOGY_START,'allocation_effect':'none'}
    df=pd.DataFrame(rows,columns=['month','pe','pb','dy']).drop_duplicates('month',keep='last').sort_values('month')
    pe=float(latest['pe']);pb=float(latest['pb']);dy=float(latest['div_yield'])
    pct={'pe_cheapness':_pct(df.pe,pe,True),'pb_cheapness':_pct(df.pb,pb,True),'dividend_yield_cheapness':_pct(df.dy,dy,False)}
    spread=max(pct.values())-min(pct.values())
    vals=[v for v in pct.values() if finite(v)];composite=float(np.mean(vals)) if vals else None
    if composite is None:label='unavailable'
    elif composite>=90:label='extremely cheap within current-methodology era'
    elif composite>=75:label='cheap within current-methodology era'
    elif composite>=60:label='below typical valuation within current-methodology era'
    elif composite>=40:label='near typical valuation within current-methodology era'
    elif composite>=25:label='above typical valuation within current-methodology era'
    else:label='expensive within current-methodology era'
    ps=_stats(df.pe);bs=_stats(df.pb);ds=_stats(df.dy)
    return {
      'status':'live' if len(df)>=MIN_MONTHS else 'limited_history',
      'months':int(len(df)),'first_month':str(df.month.iloc[0]),'last_completed_month':str(df.month.iloc[-1]),
      'methodology_start':METHODOLOGY_START,
      'methodology_note':'Common current-definition month-end observations from September 2023 only; P/B changed on 29 September 2023. Earlier P/B is excluded.',
      'allocation_effect':'none','purpose':'separate diagnostic cross-check on fixed-reference valuation core',
      'current':{'pe':pe,'pb':pb,'dividend_yield':dy},'cheapness_percentiles':pct,'composite_cheapness':composite,'label':label,
      'pe_stats':ps,'pb_stats':bs,'dividend_yield_stats':ds,
      'lens_disagreement':{'spread_pp':spread,'threshold_pp':60,'flagged':spread>=60,'interpretation':'Review signal: divergent ranks can reflect fundamentals or a data break; this does not prove a break.'},
      'vs_median_pct':{
        'pe':100*(pe/ps['median']-1) if ps and ps['median'] else None,
        'pb':100*(pb/bs['median']-1) if bs and bs['median'] else None,
        'dividend_yield':100*(dy/ds['median']-1) if ds and ds['median'] else None,
      }
    }
