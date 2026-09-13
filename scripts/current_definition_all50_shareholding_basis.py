#!/usr/bin/env python3
"""Recompute Aug-2026 NIFTY PE/PB using independent official shareholding XBRL shares.

Research only. This audit changes one variable only: total shares. The selector
is semantic and predeclared, not chosen by closeness to published ratios:
  1) `NumberOfShares` in the aggregate `ShareholdingPattern_ContextI` context;
  2) if absent, `NumberOfFullyPaidUpEquityShares` in the same aggregate context.

All earnings, net-worth, index weights, prices and dividend inputs remain exactly
as in the 50/50 integrated anchor. Partial coverage is never renormalised into a
full result. The audit therefore isolates how much of the PE/PB mismatch can be
legitimately attributed to the financial-result share-count basis.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json, math, time
import current_definition_integrated_anchor_v5 as v5
import current_definition_iwf_upper_bound_audit as iwf
import current_definition_shareholding_xbrl_audit as shx

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'current_definition_all50_shareholding_basis.json'
a=v5.a


def aggregate_share_count(facts):
    exact=[f for f in facts if f['name']=='NumberOfShares' and f['context']=='ShareholdingPattern_ContextI' and float(f['value'])>0]
    if exact:
        vals={round(float(f['value']),6) for f in exact}
        if len(vals)==1:return float(exact[0]['value']),'NumberOfShares@ShareholdingPattern_ContextI'
        raise ValueError('ambiguous_total_number_of_shares')
    exact=[f for f in facts if f['name']=='NumberOfFullyPaidUpEquityShares' and f['context']=='ShareholdingPattern_ContextI' and float(f['value'])>0]
    if exact:
        vals={round(float(f['value']),6) for f in exact}
        if len(vals)==1:return float(exact[0]['value']),'NumberOfFullyPaidUpEquityShares@ShareholdingPattern_ContextI'
        raise ValueError('ambiguous_total_fully_paid_shares')
    raise ValueError('aggregate_share_count_missing')


def anchor_record(s,row):
    # Reuse the already-audited 50/50 accounting reconstruction unchanged.
    return v5.reconstruct_one(s,row)


def main():
    s=a.cov.session();weights,wmeta=a.cov.weight_rows(s);done=[];errors=[]
    for row in weights:
        sym=row['symbol']
        try:
            base=anchor_record(s,row)
            shr_rows=iwf.shareholding_rows(s,sym);jr=shx.june_row(shr_rows)
            if not jr:raise ValueError('june_shareholding_row_missing')
            url=jr.get('xbrl')
            if not url:raise ValueError('shareholding_xbrl_url_missing')
            facts=shx.numeric_facts(shx.fetch_xml(s,url));shares,selector=aggregate_share_count(facts)
            full=float(row['price'])*shares
            if not math.isfinite(full) or full<=0:raise ValueError('invalid_shareholding_full_mcap')
            ey=float(base['ttm_profit'])/full
            by=float(base['networth'])/full
            done.append({**base,
                'financial_share_count':float(base['share_count']),
                'shareholding_share_count':shares,
                'shareholding_selector':selector,
                'shareholding_xbrl':url,
                'share_count_ratio_to_financial':shares/float(base['share_count']),
                'shareholding_full_mcap':full,
                'shareholding_earnings_yield':ey,
                'shareholding_book_yield':by,
            })
        except Exception as e:
            errors.append({'symbol':sym,'error':f'{type(e).__name__}: {e}'})
        time.sleep(.25)
    result=None
    if len(done)==50 and not errors:
        total=sum(float(x['index_mcap_cr']) for x in done)
        for x in done:x['audit_weight']=float(x['index_mcap_cr'])/total
        pe=1/sum(x['audit_weight']*x['shareholding_earnings_yield'] for x in done)
        pb=1/sum(x['audit_weight']*x['shareholding_book_yield'] for x in done)
        old_pe=1/sum(x['audit_weight']*x['earnings_yield'] for x in done)
        old_pb=1/sum(x['audit_weight']*x['book_yield'] for x in done)
        pub=a.published_ratios()
        result={
          'financial_share_basis':{'pe':old_pe,'pb':old_pb},
          'shareholding_xbrl_basis':{'pe':pe,'pb':pb},
          'published':{'pe':pub['pe'],'pb':pub['pb'],'dy':pub['dy']},
          'errors':{
            'financial_pe_relative_pct':100*abs(old_pe-pub['pe'])/pub['pe'],
            'shareholding_pe_relative_pct':100*abs(pe-pub['pe'])/pub['pe'],
            'financial_pb_relative_pct':100*abs(old_pb-pub['pb'])/pub['pb'],
            'shareholding_pb_relative_pct':100*abs(pb-pub['pb'])/pub['pb'],
          },
          'delta_from_share_basis':{'pe':pe-old_pe,'pb':pb-old_pb},
        }
    largest=sorted([
      {'symbol':x['symbol'],'weight_pct':x['published_weight_pct'],'financial_shares':x['financial_share_count'],
       'shareholding_shares':x['shareholding_share_count'],'ratio':x['share_count_ratio_to_financial']}
      for x in done],key=lambda z:abs(z['ratio']-1),reverse=True)[:15]
    out={
      'schema_version':1,'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
      'research_only':True,'anchor_date':'2026-08-31','shareholding_quarter':'2026-06-30',
      'share_selector_rule':'NumberOfShares@ShareholdingPattern_ContextI; fallback NumberOfFullyPaidUpEquityShares at same aggregate context only',
      'coverage':{'ok':len(done),'required':50,'failed':len(errors)},'failed':errors,
      'weight_source':wmeta,'result':result,'largest_share_count_differences':largest,'constituents':done,
      'interpretation_guardrail':'This is a one-variable attribution audit. It does not authorize choosing share counts, earnings, net worth, IWFs, or tolerances by closeness to published ratios.',
      'live_model_changed':False,'live_allocation_changed':False,'tolerances_changed':False,
    }
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print(json.dumps({'coverage':out['coverage'],'result':result,'largest_share_count_differences':largest},indent=2))

if __name__=='__main__':main()
