#!/usr/bin/env python3
"""Strict integrated anchor v2: fixed PIT dates and signed denominator facts.

Supersedes the v1 runner without altering live-model files. Fixes ISO date
parsing so future filings cannot be admitted by day/month inversion, and keeps
negative constituent earnings/book values in the index denominator as required
by NIFTY index-ratio aggregation. All other source/tolerance safeguards from v1
remain in force.
"""
from __future__ import annotations
import math,re,time
import pandas as pd
import current_definition_integrated_anchor as a


def parse_dt(x):
    if x is None or str(x).strip()=='':return None
    s=str(x).strip()
    try:
        if re.match(r'^\d{4}-\d{2}-\d{2}(?:[ T]|$)',s):
            d=pd.to_datetime(s,dayfirst=False,errors='coerce')
        else:
            d=pd.to_datetime(s,dayfirst=True,errors='coerce')
    except Exception:return None
    return None if pd.isna(d) else d

# All v1 functions resolve parse_dt from module globals at call time.
a.parse_dt=parse_dt


def networth_from(fs):
    # Net worth is an additive index denominator. Do not discard a constituent
    # merely because book value is zero/negative; preserve the signed fact.
    f=a.pick(fs,a.EQUITY_NAMES,['OneI'])
    if f is not None and math.isfinite(float(f['value'])):return f,'direct'
    cap=a.pick(fs,a.CAP_NAMES,['OneI']);other=a.pick(fs,a.OTHER_EQUITY_NAMES,['OneI'])
    if cap and other and cap['value']>0 and all(math.isfinite(float(x['value'])) for x in (cap,other)):
        return {'name':cap['name']+'+'+other['name'],'context':'OneI','value':cap['value']+other['value']},'capital_plus_other_equity'
    icap=a.pick(fs,['PaidUpEquityShareCapital'],['OneI'])
    reserve=a.pick(fs,a.INSURANCE_RESERVE_NAMES,['OneI','OneD','FourD'])
    fv=a.pick(fs,a.INSURANCE_FV_NAMES,['OneI','OneD','FourD'])
    if icap and reserve and icap['value']>0 and math.isfinite(float(reserve['value'])):
        value=icap['value']+reserve['value']+(fv['value'] if fv and math.isfinite(float(fv['value'])) else 0.0)
        names=[icap['name'],reserve['name']]+([fv['name']] if fv else [])
        return {'name':'+'.join(names),'context':'insurance_shareholders_fund','value':value},'insurance_shareholders_fund'
    raise ValueError('networth_fact_missing')

a.networth_from=networth_from


def reconstruct_one(s,row):
    listings,issuer=a.listings_for(s,row);selected={};basis={}
    for q in a.TARGET:
        r,b=a.choose_quarter(listings,q)
        if not r:raise ValueError('missing_integrated_quarter_'+q)
        selected[q]=r;basis[q]=b
    parsed={}
    for q in a.TARGET:
        parsed[q]=a.numeric_facts(a.fetch_xml(s,selected[q]['xbrl']));time.sleep(.20)
    profits=[];profit_meta=[]
    for q in a.TARGET:
        f=a.profit_from(parsed[q]);profits.append(f['value']);profit_meta.append({'quarter':q,'basis':basis[q],'tag':f['name'],'context':f['context'],'filing_time':str(a.filing_time(selected[q])),'xbrl':selected[q]['xbrl']})
    c=a.capital_from(parsed['30-JUN-2026'])
    actions=a.corporate_actions(s,row['symbol'])
    fv=a.face_from_xbrl(parsed['30-JUN-2026']);face_source='xbrl'
    if fv is None:
        fv=a.face_from_actions(actions);face_source='NSE_corporate_actions_agreeing_faceVal'
    if fv is None or fv['value']<=0:raise ValueError('face_value_missing_or_ambiguous')
    shares=c['value']/fv['value']
    nw,nwmode=networth_from(parsed['31-MAR-2026'])
    if shares<=0 or not math.isfinite(float(nw['value'])):raise ValueError('invalid_structure')
    full_mcap=row['price']*shares;ttm=sum(profits)
    if full_mcap<=0 or not math.isfinite(float(ttm)):raise ValueError('invalid_earnings_or_mcap')
    dps,divs=a.dividends_from_actions(actions,fv['value'])
    return {**row,'status':'ok','issuer_used':issuer,'basis_by_quarter':basis,'ttm_profit':ttm,'share_count':shares,'paid_up_capital':c['value'],'face_value':fv['value'],'capital_tag':c['name'],'face_tag':fv['name'],'face_source':face_source,'full_mcap':full_mcap,'earnings_yield':ttm/full_mcap,'networth':nw['value'],'networth_tag':nw['name'],'networth_mode':nwmode,'book_yield':nw['value']/full_mcap,'dividend_ps_12m':dps,'dividend_yield_pct':100*dps/row['price'],'profit_quarters':profit_meta,'dividends':divs}

a.reconstruct_one=reconstruct_one

if __name__=='__main__':
    a.main()
