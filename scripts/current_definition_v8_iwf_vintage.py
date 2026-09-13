#!/usr/bin/env python3
"""V8 IWF-vintage audit for the 31-Aug-2026 anchor.

Uses the same official Aug-2026 free-float market cap, price and Jun-2026 total
shares as the V8 upper-bound audit. It changes only the PUBLIC-SHAREHOLDING
comparison vintage: 31-Mar-2026 vs 30-Jun-2026.

This does NOT assert which vintage Nifty used. It asks whether residual
hard-bound breaches are consistent with a quarterly IWF update lag. Public
shareholding remains an upper bound, never an IWF substitute. Displayed
shareholding percentages are treated as rounded, not exact.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json, time
import pandas as pd
import current_definition_v8_iwf_bound as b

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'current_definition_v8_iwf_vintage.json'


def quarter(rows,when):
    target=pd.Timestamp(when).date()
    for r in rows:
        d=b.dt(r.get('date') or r.get('asOnDate') or r.get('as_on_date'))
        if d is not None and d.date()==target:return r
    return None


def main():
    s=b.session();weights,wmeta=b.weight_rows(s);done=[];errors=[]
    for row in weights:
        sym=row['symbol']
        try:
            rows=b.share_rows(s,sym);mar=quarter(rows,'2026-03-31');jun=quarter(rows,'2026-06-30')
            if not mar or not jun:raise ValueError('march_or_june_shareholding_missing')
            url=jun.get('xbrl')
            if not url:raise ValueError('june_shareholding_xbrl_missing')
            _,shares,_=b.total_shares(b.xroot(s,url));point,lo,hi=b.interval(row,shares)
            mar_raw=mar.get('public_val');jun_raw=jun.get('public_val')
            mp=b.fnum(mar_raw);jp=b.fnum(jun_raw);mint=b.displayed_interval(mar_raw);jint=b.displayed_interval(jun_raw)
            if mp is None or jp is None or mint is None or jint is None:raise ValueError('public_pct_missing')
            mlo,mhi,mhalf=mint;jlo,jhi,jhalf=jint
            done.append({**row,'shareholding_total_shares_june':shares,'implied_iwf':point,'implied_iwf_min':lo,'implied_iwf_max':hi,
                         'public_pct_mar':mp,'public_pct_mar_min':mlo,'public_pct_mar_max':mhi,'public_pct_mar_half_step_pp':mhalf,
                         'public_pct_jun':jp,'public_pct_jun_min':jlo,'public_pct_jun_max':jhi,'public_pct_jun_half_step_pp':jhalf,
                         'public_change_pp_jun_minus_mar':jp-mp,
                         'breach_vs_mar':bool(lo>mhi/100.0),'breach_vs_jun':bool(lo>jhi/100.0),
                         'margin_to_mar_public_pp':mp-100*point,'margin_to_jun_public_pp':jp-100*point,
                         'margin_to_mar_public_upper_pp':mhi-100*lo,'margin_to_jun_public_upper_pp':jhi-100*lo})
        except Exception as e:errors.append({'symbol':sym,'error':f'{type(e).__name__}: {e}'})
        time.sleep(.15)
    done=sorted(done,key=lambda x:x['symbol']);bm=[x for x in done if x['breach_vs_mar']];bj=[x for x in done if x['breach_vs_jun']]
    tot=sum(x['index_mcap_cr'] for x in done) or 1
    def block(xs):return {'count':len(xs),'index_weight_pct':100*sum(x['index_mcap_cr'] for x in xs)/tot,'symbols':[x['symbol'] for x in xs]}
    changed=[{'symbol':x['symbol'],'public_mar':x['public_pct_mar'],'public_jun':x['public_pct_jun'],'change_pp':x['public_change_pp_jun_minus_mar'],
              'implied_iwf_pct':100*x['implied_iwf'],'breach_mar':x['breach_vs_mar'],'breach_jun':x['breach_vs_jun']} for x in done if x['breach_vs_mar']!=x['breach_vs_jun']]
    out={'schema_version':2,'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'research_only':True,
         'anchor_date':'2026-08-31','coverage':{'ok':len(done),'required':50,'failed':len(errors)},'failed':errors,
         'breaches_vs_mar_public':block(bm),'breaches_vs_jun_public':block(bj),'breach_status_changes':changed,'weight_source':wmeta,
         'interpretation_guardrail':'Timing-consistency audit only. Displayed public-shareholding percentages are treated as rounded. A non-breach versus a vintage does not prove that vintage supplied index IWF; it only shows compatibility with that vintage public-shareholding upper bound.',
         'constituents':done,'live_model_changed':False,'live_allocation_changed':False,'tolerances_changed':False}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print(json.dumps({'coverage':out['coverage'],'breaches_vs_mar_public':out['breaches_vs_mar_public'],
                      'breaches_vs_jun_public':out['breaches_vs_jun_public'],'breach_status_changes':changed},indent=2))

if __name__=='__main__':main()
