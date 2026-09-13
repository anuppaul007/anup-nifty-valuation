#!/usr/bin/env python3
"""Audit inferred Aug-2026 NIFTY IWFs against official June public shareholding.

Research only. This is a falsification/diagnostic layer, not a replacement
formula. The NIFTY monthly report gives free-float index market cap and price.
Combined with the PIT statutory share count reconstructed from NSE Integrated
Filings, that implies an IWF. Official June-2026 NSE shareholding gives a hard
upper bound: IWF cannot exceed public shareholding, because additional strategic
categories can only reduce free float.

Rounding is handled as an interval rather than an arbitrary tolerance: published
price and market-cap fields are assumed rounded to their displayed precision.
If even the minimum possible inferred IWF exceeds public shareholding, the
statutory share count cannot be the exact operational index-share basis.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import json,math,time
import pandas as pd
import current_definition_integrated_anchor_v5 as v5

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'current_definition_iwf_upper_bound_audit.json'
a=v5.a
ANCHOR=pd.Timestamp('2026-08-31 23:59:59')


def fnum(x):
    try:return float(str(x).replace(',','').replace('%','').strip())
    except Exception:return None


def shareholding_rows(s,symbol):
    url='https://www.nseindia.com/api/corporate-share-holdings-master'
    p={'index':'equities','symbol':symbol}
    last=None
    for attempt in range(5):
        try:
            r=s.get(url,params=p,headers={**a.UA,'referer':f'https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern?symbol={symbol}&tabIndex=equity'},timeout=30)
            if r.status_code in (401,403,500):
                try:s.get('https://www.nseindia.com/',timeout=15)
                except Exception:pass
                time.sleep(1+attempt);continue
            r.raise_for_status();d=r.json();return d if isinstance(d,list) else d.get('data',[]) if isinstance(d,dict) else []
        except Exception as e:last=e;time.sleep(1+attempt)
    raise last or RuntimeError('shareholding_unavailable')


def parse_dt(x):
    d=pd.to_datetime(str(x),dayfirst=True,errors='coerce')
    return None if pd.isna(d) else d


def june_public_fraction(rows):
    candidates=[]
    for r in rows:
        dt=parse_dt(r.get('date') or r.get('asOnDate') or r.get('as_on_date'))
        if dt is None or dt.date()!=pd.Timestamp('2026-06-30').date():continue
        pub=fnum(r.get('public_val') if 'public_val' in r else r.get('public'))
        prom=fnum(r.get('pr_and_prgrp') if 'pr_and_prgrp' in r else r.get('promoter'))
        emp=fnum(r.get('employeeTrusts'))
        if pub is not None:candidates.append((r,pub,prom,emp))
    if not candidates:return None
    # Any revision/broadcast metadata can differ; API returns latest first. Use
    # first exact June quarter, which is the current official record for it.
    r,pub,prom,emp=candidates[0]
    return {'public_fraction':pub/100.0,'public_pct':pub,'promoter_pct':prom,'employee_trust_pct':emp,'raw':r}


def decimals(x):
    s=str(x)
    return len(s.split('.',1)[1]) if '.' in s else 0


def rounding_half_unit(x):
    return .5*(10**(-decimals(x)))


def implied_interval(row,shares):
    # FF market cap in the monthly PDF is in crore rupees; price is rupees.
    mc=float(row['index_mcap_cr']);px=float(row['price']);n=float(shares)
    mc_h=rounding_half_unit(row['index_mcap_cr']);px_h=rounding_half_unit(row['price'])
    mc_lo=max(0.0,mc-mc_h)*1e7;mc_hi=(mc+mc_h)*1e7
    px_lo=max(1e-12,px-px_h);px_hi=px+px_h
    point=mc*1e7/(px*n)
    lo=mc_lo/(px_hi*n);hi=mc_hi/(px_lo*n)
    return point,lo,hi,{'mcap_half_rounding_cr':mc_h,'price_half_rounding':px_h}


def statutory_structure(s,row):
    listings,issuer=a.listings_for(s,row);parsed={}
    for q in ('31-MAR-2026','30-JUN-2026'):
        sel,basis=a.choose_quarter(listings,q)
        if not sel:raise ValueError('missing_'+q)
        parsed[q]=a.numeric_facts(a.fetch_xml(s,sel['xbrl']));time.sleep(.18)
    actions=a.corporate_actions(s,row['symbol'])
    c,fv,src,structure,attempts=v5.choose_structure(row,parsed,actions)
    return {'shares':structure['shares'],'share_source':src,'paid_up_capital':c['value'],'face_value':fv['value'],'issuer':issuer,'attempts':attempts}


def main():
    s=a.cov.session();weights,wmeta=a.cov.weight_rows(s);done=[];errors=[]
    for row in weights:
        try:
            st=statutory_structure(s,row)
            sh=june_public_fraction(shareholding_rows(s,row['symbol']))
            if sh is None:raise ValueError('june_2026_shareholding_missing')
            point,lo,hi,rnd=implied_interval(row,st['shares']);pub=sh['public_fraction']
            done.append({**row,**st,**sh,'implied_iwf_point':point,'implied_iwf_min':lo,'implied_iwf_max':hi,
                         'public_minus_implied_point_pp':100*(pub-point),
                         'hard_upper_bound_breach':bool(lo>pub),
                         'rounding_assumptions':rnd})
        except Exception as e:errors.append({'symbol':row['symbol'],'error':f'{type(e).__name__}: {e}'})
        time.sleep(.20)
    done=sorted(done,key=lambda x:x['symbol']);breaches=[x for x in done if x['hard_upper_bound_breach']]
    weight_total=sum(float(x['index_mcap_cr']) for x in done) or 1
    breach_weight=100*sum(float(x['index_mcap_cr']) for x in breaches)/weight_total
    out={
      'schema_version':1,'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
      'research_only':True,'anchor_date':'2026-08-31','shareholding_quarter':'2026-06-30',
      'logic':'June public shareholding is a hard upper bound, not an IWF estimate. Strategic/non-free-float public categories may make true IWF lower. A breach is flagged only if the entire rounding interval for inferred IWF is above official public shareholding.',
      'official_timing_note':'NSE Indices methodology can implement index-share/IWF changes on monthly or quarterly schedules, so statutory paid-up shares need not equal operational index shares at the anchor.',
      'coverage':{'ok':len(done),'required':50,'failed':len(errors)},'failed':errors,
      'breaches':{'count':len(breaches),'index_weight_pct':breach_weight,'symbols':[x['symbol'] for x in breaches]},
      'weight_source':wmeta,'constituents':done,
      'interpretation_guardrail':'This audit can falsify a statutory-share basis for specific constituents. It must not replace IWF with public shareholding or tune factors to published index PE/PB.',
      'live_model_changed':False,'live_allocation_changed':False,'tolerances_changed':False,
    }
    OUT.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'coverage':out['coverage'],'breaches':out['breaches'],'largest_negative_gaps':sorted([{'symbol':x['symbol'],'gap_pp':x['public_minus_implied_point_pp'],'weight_pct':x['published_weight_pct']} for x in done],key=lambda z:z['gap_pp'])[:15]},indent=2))

if __name__=='__main__':main()
