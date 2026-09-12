#!/usr/bin/env python3
"""Strict integrated anchor v5: PIT share-count hierarchy with identity checks.

Share count is reconstructed from paid-up ordinary equity capital / rupee face
value. Current-quarter facts are preferred, with official NSE corporate-action
face value cross-check/fallback. A candidate is accepted only if the implied
total company market cap is >= the official NIFTY free-float market cap for the
same date. If the current-quarter capital structure violates that identity,
fall back to the latest PIT annual (Mar-2026) capital/face facts and apply the
same check. This resolves malformed June facts without stock-specific values.
"""
from __future__ import annotations
import math,time
import current_definition_integrated_anchor_v4 as v4

a=v4.a
v3=v4.v3


def _structure(row,capital,face):
    if capital is None or face is None:return None
    try:c=float(capital['value']);f=float(face['value'])
    except Exception:return None
    if not (math.isfinite(c) and math.isfinite(f) and c>0 and f>0):return None
    shares=c/f;full=float(row['price'])*shares;ff=float(row['index_mcap_cr'])*1e7
    if not (math.isfinite(full) and full>0):return None
    # Free-float market cap is a subset of total market cap. Tiny allowance is
    # numerical only, not an empirical threshold.
    if full + max(1.0,ff)*1e-9 < ff:return None
    return {'shares':shares,'full_mcap':full,'free_float_fraction':ff/full}


def _face_candidates(fs,actions):
    out=[]
    act=a.face_from_actions(actions)
    x=a.face_from_xbrl(fs)
    if act is not None:out.append((act,'NSE_corporate_actions_faceVal'))
    if x is not None:
        if not out or abs(float(x['value'])-float(out[0][0]['value']))>1e-9:
            out.append((x,'xbrl_face'))
        else:
            out[0]=(out[0][0],'NSE_actions_and_xbrl_agree')
    return out


def choose_structure(row,parsed,actions):
    attempts=[]
    # 1) Current-quarter paid-up capital, preferred for post-annual issuance.
    current_cap=a.capital_from(parsed['30-JUN-2026'])
    for face,src in _face_candidates(parsed['30-JUN-2026'],actions):
        st=_structure(row,current_cap,face);attempts.append({'period':'30-JUN-2026','capital':current_cap['value'],'face':face['value'],'source':src,'valid':st is not None})
        if st:return current_cap,face,'current_quarter_'+src,st,attempts
    # 2) Latest annual PIT capital structure. March facts are available by the
    # Aug-31 anchor and are used only when every current candidate is impossible.
    annual_cap=a.capital_from(parsed['31-MAR-2026'])
    annual_faces=[]
    ax=a.face_from_xbrl(parsed['31-MAR-2026'])
    if ax is not None:annual_faces.append((ax,'annual_xbrl_face'))
    act=a.face_from_actions(actions)
    if act is not None and (not annual_faces or abs(float(act['value'])-float(annual_faces[0][0]['value']))>1e-9):annual_faces.append((act,'annual_cap_plus_NSE_action_face'))
    for face,src in annual_faces:
        st=_structure(row,annual_cap,face);attempts.append({'period':'31-MAR-2026','capital':annual_cap['value'],'face':face['value'],'source':src,'valid':st is not None})
        if st:return annual_cap,face,src,st,attempts
    raise ValueError('no_structurally_valid_share_count_basis')


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
    actions=a.corporate_actions(s,row['symbol'])
    c,fv,share_source,structure,attempts=choose_structure(row,parsed,actions)
    shares=structure['shares'];full_mcap=structure['full_mcap']
    nw,nwmode=a.networth_from(parsed['31-MAR-2026'])
    if not math.isfinite(float(nw['value'])):raise ValueError('invalid_networth')
    ttm=sum(profits)
    if not math.isfinite(float(ttm)):raise ValueError('invalid_earnings')
    dps,divs=a.dividends_from_actions(actions,fv['value'])
    return {**row,'status':'ok','issuer_used':issuer,'basis_by_quarter':basis,'ttm_profit':ttm,'share_count':shares,'share_count_source':share_source,'share_count_attempts':attempts,'paid_up_capital':c['value'],'face_value':fv['value'],'capital_tag':c['name'],'face_tag':fv['name'],'full_mcap':full_mcap,'free_float_fraction_check':structure['free_float_fraction'],'earnings_yield':ttm/full_mcap,'networth':nw['value'],'networth_tag':nw['name'],'networth_mode':nwmode,'book_yield':nw['value']/full_mcap,'dividend_ps_12m':dps,'dividend_yield_pct':100*dps/row['price'],'profit_quarters':profit_meta,'dividends':divs}

a.reconstruct_one=reconstruct_one

if __name__=='__main__':
    a.main()
