#!/usr/bin/env python3
"""Definition audit for the strict 31-Aug-2026 current-definition anchor.

Research only. The 50/50 anchor is deliberately kept failed unless the original
predeclared tolerances are met. This script does not choose the closest formula.
It evaluates a small set of accounting hypotheses fixed from financial-statement
semantics to explain the mismatch:

PE H0: owners-of-parent PAT (current strict runner).
PE H1: reported period PAT/net-profit line when available, otherwise H0.
PB H0: current strict shareholder-net-worth rule.
PB H1: direct NetWorth/TotalEquity, then owners+NCI, otherwise H0.

It also audits March OneD versus FourD contexts to detect accidental annual/
quarter double counting, and records why dividend yield needs ex-date free-float
factors rather than current weights before any formula change is considered.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import json,math,time
import pandas as pd
import current_definition_integrated_anchor_v5 as v5

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'current_definition_definition_audit.json'
a=v5.a

PERIOD_PAT_NAMES=[
 'ProfitLossForPeriod','ProfitLossForThePeriod',
 'ProfitLossForPeriodFromContinuingAndDiscontinuedOperations',
 'ProfitLossFromOrdinaryActivitiesAfterTax',
 'ProfitLossAfterTaxAndExtraordinaryItems',
 'ProfitLossAfterTaxBeforeExtraordinaryItems','ProfitAfterTax'
]
OWNER_PAT_NAMES=['ProfitOrLossAttributableToOwnersOfParent']
TOTAL_EQUITY_NAMES=['NetWorth','TotalEquity','Equity']
OWNER_EQUITY_NAMES=['EquityAttributableToOwnersOfParent','TotalEquityAttributableToOwnersOfParent']
NCI_NAMES=['NonControllingInterest','NonControllingInterests','NonControllingInterestsInEquity']


def finite(x):
    try:return x is not None and math.isfinite(float(x))
    except Exception:return False


def pick(fs,names,contexts):
    return a.pick(fs,names,contexts)


def value(f):return float(f['value']) if f and finite(f.get('value')) else None


def profit_hypotheses(fs):
    owner=pick(fs,OWNER_PAT_NAMES,['OneD'])
    period=pick(fs,PERIOD_PAT_NAMES,['OneD'])
    current=a.profit_from(fs)
    return {
      'current_owner_preferred':value(current),
      'reported_period_pat_preferred':value(period) if value(period) is not None else value(current),
      'owner_tag':owner['name'] if owner else None,
      'period_tag':period['name'] if period else None,
    }


def book_hypotheses(fs):
    current,mode=a.networth_from(fs)
    direct=pick(fs,TOTAL_EQUITY_NAMES,['OneI'])
    owner=pick(fs,OWNER_EQUITY_NAMES,['OneI'])
    nci=pick(fs,NCI_NAMES,['OneI'])
    broader=None;broader_source=None
    if direct and value(direct)>0:
        broader=value(direct);broader_source=direct['name']
    elif owner and value(owner)>0 and nci and value(nci)>=0:
        broader=value(owner)+value(nci);broader_source=owner['name']+'+'+nci['name']
    else:
        broader=value(current);broader_source='current_rule_fallback:'+mode
    return {
      'current':value(current),'current_source':current['name'],'current_mode':mode,
      'broader_equity':broader,'broader_source':broader_source,
      'owner_equity':value(owner),'nci':value(nci),'direct_total_or_networth':value(direct),
    }


def march_context_audit(fs,selected_name):
    one=pick(fs,[selected_name],['OneD']) if selected_name else None
    four=pick(fs,[selected_name],['FourD']) if selected_name else None
    ratio=None
    if one and four and finite(one['value']) and finite(four['value']) and float(four['value'])!=0:
        ratio=float(one['value'])/float(four['value'])
    return {'tag':selected_name,'oneD':value(one),'fourD':value(four),'oneD_over_fourD':ratio}


def reconstruct_one(s,row):
    listings,issuer=a.listings_for(s,row);selected={};basis={};parsed={}
    for q in a.TARGET:
        r,b=a.choose_quarter(listings,q)
        if not r:raise ValueError('missing_integrated_quarter_'+q)
        selected[q]=r;basis[q]=b
    for q in a.TARGET:
        parsed[q]=a.numeric_facts(a.fetch_xml(s,selected[q]['xbrl']));time.sleep(.18)
    profits0=[];profits1=[];quarter_meta=[]
    for q in a.TARGET:
        h=profit_hypotheses(parsed[q]);profits0.append(h['current_owner_preferred']);profits1.append(h['reported_period_pat_preferred'])
        chosen=a.profit_from(parsed[q])
        quarter_meta.append({'quarter':q,'basis':basis[q],'current_tag':chosen['name'],'period_tag':h['period_tag'],'current_value':h['current_owner_preferred'],'period_hypothesis_value':h['reported_period_pat_preferred']})
    actions=a.corporate_actions(s,row['symbol'])
    c,fv,share_source,structure,attempts=v5.choose_structure(row,parsed,actions)
    books=book_hypotheses(parsed['31-MAR-2026'])
    dps,divs=a.dividends_from_actions(actions,fv['value'])
    march=march_context_audit(parsed['31-MAR-2026'],a.profit_from(parsed['31-MAR-2026'])['name'])
    return {
      **row,'status':'ok','issuer_used':issuer,'basis_by_quarter':basis,
      'share_count':structure['shares'],'share_count_source':share_source,'full_mcap':structure['full_mcap'],
      'free_float_fraction_check':structure['free_float_fraction'],
      'ttm_profit_current':sum(profits0),'ttm_profit_period_hypothesis':sum(profits1),
      'book_current':books['current'],'book_broader_hypothesis':books['broader_equity'],
      'book_detail':books,'march_context_audit':march,'profit_quarters':quarter_meta,
      'dividend_ps_12m':dps,'dividend_yield_pct_current_weight_approx':100*dps/row['price'],'dividends':divs,
      'structure_attempts':attempts,
    }


def aggregate(done,pub):
    total=sum(float(x['index_mcap_cr']) for x in done)
    for x in done:x['weight']=float(x['index_mcap_cr'])/total
    def pe(field):
        den=sum(x['weight']*(float(x[field])/float(x['full_mcap'])) for x in done)
        return 1/den
    def pb(field):
        den=sum(x['weight']*(float(x[field])/float(x['full_mcap'])) for x in done)
        return 1/den
    dy=sum(x['weight']*float(x['dividend_yield_pct_current_weight_approx']) for x in done)
    vals={
      'pe_current':pe('ttm_profit_current'),
      'pe_reported_period_pat_hypothesis':pe('ttm_profit_period_hypothesis'),
      'pb_current':pb('book_current'),
      'pb_broader_equity_hypothesis':pb('book_broader_hypothesis'),
      'dy_current_weight_approx':dy,
    }
    errs={
      'pe_current_relative_pct':100*abs(vals['pe_current']-pub['pe'])/pub['pe'],
      'pe_period_hypothesis_relative_pct':100*abs(vals['pe_reported_period_pat_hypothesis']-pub['pe'])/pub['pe'],
      'pb_current_relative_pct':100*abs(vals['pb_current']-pub['pb'])/pub['pb'],
      'pb_broader_hypothesis_relative_pct':100*abs(vals['pb_broader_equity_hypothesis']-pub['pb'])/pub['pb'],
      'dy_current_weight_absolute_pp':abs(vals['dy_current_weight_approx']-pub['dy']),
    }
    return vals,errs


def main():
    s=a.cov.session();rows,weight_meta=a.cov.weight_rows(s);done=[];errors=[]
    for row in rows:
        try:done.append(reconstruct_one(s,row))
        except Exception as e:errors.append({'symbol':row['symbol'],'error':f'{type(e).__name__}: {e}'})
        time.sleep(.20)
    done=sorted(done,key=lambda x:x['symbol']);pub=a.published_ratios();agg=errs=None
    if len(done)==50 and not errors:agg,errs=aggregate(done,pub)
    ratios=[x['march_context_audit']['oneD_over_fourD'] for x in done if finite(x['march_context_audit'].get('oneD_over_fourD'))]
    suspicious=[{'symbol':x['symbol'],**x['march_context_audit']} for x in done if finite(x['march_context_audit'].get('oneD_over_fourD')) and abs(float(x['march_context_audit']['oneD_over_fourD']))>=0.75]
    out={
      'schema_version':1,'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
      'research_only':True,'anchor_date':'2026-08-31','predeclared_anchor_tolerances':a.TOL,
      'hypotheses_predefined':{
        'pe_h0':'owners-of-parent/current strict PAT selection','pe_h1':'reported period PAT/net-profit OneD line when available, otherwise H0',
        'pb_h0':'current strict shareholder-net-worth rule','pb_h1':'direct NetWorth/TotalEquity, then owners+NCI, otherwise H0',
        'dy':'No alternate formula promoted. Current-weight DPS approximation is diagnostic because official rolling gross dividend is adjusted using index/free-float factors at ex-date.'
      },
      'weight_source':weight_meta,'coverage':{'ok':len(done),'required':50,'failed':len(errors)},'failed_constituents':errors,
      'published':{'pe':pub['pe'],'pb':pub['pb'],'dy':pub['dy'],'raw':pub['raw']},
      'aggregate_hypotheses':agg,'errors_vs_published':errs,
      'march_context_audit':{'ratios_available':len(ratios),'median_oneD_over_fourD':float(pd.Series(ratios).median()) if ratios else None,'suspicious_abs_ratio_ge_0_75':suspicious},
      'dividend_methodology_gap':'Official DY cumulates rolling-12m constituent dividends adjusted for free-float/capping factors. Applying today\'s weight to historical DPS is not exact when IWF/shares changed between ex-date and anchor; ex-date factor reconstruction is required before changing the DY formula.',
      'constituents':done,'live_model_changed':False,'live_allocation_changed':False,'tolerances_changed':False,
    }
    OUT.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'coverage':out['coverage'],'published':out['published'],'aggregate_hypotheses':agg,'errors':errs,'march_context':out['march_context_audit']},indent=2))

if __name__=='__main__':main()
