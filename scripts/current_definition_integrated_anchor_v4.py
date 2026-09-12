#!/usr/bin/env python3
"""Strict integrated anchor v4: authoritative face-value hierarchy.

The standardized NSE XBRL occasionally exposes values under a face-value tag
that are plainly not per-share face values (observed for Bajaj Finserv and
Bharti Airtel). For valuation reconstruction, prefer an agreeing positive
`faceVal` from official NSE corporate-action records when available; otherwise
fall back to the XBRL fact. All other v3 point-in-time, taxonomy, coverage and
tolerance rules remain unchanged.
"""
from __future__ import annotations
import time
import current_definition_integrated_anchor_v3 as v3

a=v3.a


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
    action_fv=a.face_from_actions(actions)
    xbrl_fv=a.face_from_xbrl(parsed['30-JUN-2026'])
    if action_fv is not None:
        fv=action_fv;face_source='NSE_corporate_actions_agreeing_faceVal'
    elif xbrl_fv is not None:
        fv=xbrl_fv;face_source='xbrl_no_action_face_available'
    else:
        raise ValueError('face_value_missing_or_ambiguous')
    shares=c['value']/fv['value']
    nw,nwmode=a.networth_from(parsed['31-MAR-2026'])
    if shares<=0 or nw['value']<=0:raise ValueError('nonpositive_structure')
    full_mcap=row['price']*shares;ttm=sum(profits)
    if full_mcap<=0:raise ValueError('nonpositive_mcap')
    dps,divs=a.dividends_from_actions(actions,fv['value'])
    return {**row,'status':'ok','issuer_used':issuer,'basis_by_quarter':basis,'ttm_profit':ttm,'share_count':shares,'paid_up_capital':c['value'],'face_value':fv['value'],'capital_tag':c['name'],'face_tag':fv['name'],'face_source':face_source,'xbrl_face_value':(xbrl_fv['value'] if xbrl_fv else None),'face_disagreement':(xbrl_fv is not None and abs(float(xbrl_fv['value'])-float(fv['value']))>1e-9),'full_mcap':full_mcap,'earnings_yield':ttm/full_mcap,'networth':nw['value'],'networth_tag':nw['name'],'networth_mode':nwmode,'book_yield':nw['value']/full_mcap,'dividend_ps_12m':dps,'dividend_yield_pct':100*dps/row['price'],'profit_quarters':profit_meta,'dividends':divs}


a.reconstruct_one=reconstruct_one
v3.a.reconstruct_one=reconstruct_one

if __name__=='__main__':
    a.main()
