#!/usr/bin/env python3
"""Audit latest official annual report available by the 31-Aug-2026 P/B anchor.

Current Nifty Indices P/B methodology specifies net worth from each constituent's
annual financial report (consolidated; standalone fallback only if consolidated
financials are unavailable). This script establishes the point-in-time annual-
report source set before any PDF/net-worth extraction is attempted.

Research only. No report is selected by closeness to published P/B.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json, time
import pandas as pd
import current_definition_integrated_coverage as cov

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'current_definition_annual_report_availability.json'
ANCHOR=pd.Timestamp('2026-08-31 23:59:59')
URL='https://www.nseindia.com/api/annual-reports'


def dt(x):
    if not x:return None
    d=pd.to_datetime(str(x),dayfirst=True,errors='coerce')
    return None if pd.isna(d) else d


def annual_rows(s,symbol):
    p={'index':'equities','symbol':symbol}
    last=None
    for attempt in range(5):
        try:
            r=s.get(URL,params=p,headers={**cov.UA,'referer':f'https://www.nseindia.com/companies-listing/corporate-filings-annual-reports?symbol={symbol}&tabIndex=equity'},timeout=30)
            if r.status_code in (401,403,500):
                try:s.get('https://www.nseindia.com/',timeout=15)
                except Exception:pass
                time.sleep(1+attempt);continue
            r.raise_for_status();d=r.json()
            # Current API normally returns {'data': [...]} but older wrappers
            # expose nested lists; flatten conservatively without inventing rows.
            if isinstance(d,list):return d
            if isinstance(d,dict):
                if isinstance(d.get('data'),list):return d['data']
                rows=[]
                for v in d.values():
                    if isinstance(v,list):rows.extend(x for x in v if isinstance(x,dict))
                return rows
            return []
        except Exception as e:last=e;time.sleep(1+attempt)
    raise last or RuntimeError('annual_reports_unavailable')


def broadcast(row):
    for k in ('broadcast_dttm','broadcastDate','broadcastDateTime','disseminationDateTime','date'):
        d=dt(row.get(k))
        if d is not None:return d
    return None


def report_years(row):
    fy=row.get('fromYear') or row.get('from_year') or row.get('fromYr') or row.get('fromyear')
    ty=row.get('toYear') or row.get('to_year') or row.get('toYr') or row.get('toyear')
    try:fy=int(fy)
    except Exception:fy=None
    try:ty=int(ty)
    except Exception:ty=None
    return fy,ty


def file_url(row):
    for k in ('fileName','file_name','attachment','attchmntFile','url'):
        v=row.get(k)
        if isinstance(v,str) and v.startswith('http'):return v
    return None


def main():
    s=cov.session();weights,wmeta=cov.weight_rows(s);done=[];errors=[]
    for row in weights:
        sym=row['symbol']
        try:
            rows=annual_rows(s,sym);eligible=[]
            for rr in rows:
                b=broadcast(rr);fy,ty=report_years(rr);url=file_url(rr)
                if b is not None and b<=ANCHOR and url:
                    eligible.append({'from_year':fy,'to_year':ty,'broadcast':str(b),'url':url,'raw':rr})
            eligible=sorted(eligible,key=lambda x:(x['to_year'] or -1,pd.Timestamp(x['broadcast'])),reverse=True)
            chosen=eligible[0] if eligible else None
            done.append({**row,'api_row_count':len(rows),'eligible_report_count':len(eligible),'latest_pit_report':chosen,
                         'has_2025_26_by_anchor':bool(chosen and chosen.get('from_year')==2025 and chosen.get('to_year')==2026)})
        except Exception as e:errors.append({'symbol':sym,'error':f'{type(e).__name__}: {e}'})
        time.sleep(.2)
    done=sorted(done,key=lambda x:x['symbol']);latest_2026=[x for x in done if x['has_2025_26_by_anchor']]
    no_report=[x for x in done if x['latest_pit_report'] is None]
    older=[x for x in done if x['latest_pit_report'] is not None and not x['has_2025_26_by_anchor']]
    out={'schema_version':1,'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'research_only':True,
         'anchor_date':'2026-08-31','methodology_requirement':'net worth from annual financial report; consolidated financials preferred, standalone fallback only if consolidated unavailable',
         'endpoint':URL,'weight_source':wmeta,'coverage':{'api_ok':len(done),'required':50,'failed':len(errors),'fy2025_26_available_by_anchor':len(latest_2026),'older_latest_report':len(older),'no_pit_report':len(no_report)},
         'failed':errors,'older_latest_symbols':[{'symbol':x['symbol'],'latest':x['latest_pit_report']} for x in older],
         'no_pit_report_symbols':[x['symbol'] for x in no_report],'constituents':done,
         'interpretation_guardrail':'Availability only. No PDF number is parsed and no annual report is chosen by closeness to NIFTY P/B.',
         'live_model_changed':False,'live_allocation_changed':False,'tolerances_changed':False}
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print(json.dumps({'coverage':out['coverage'],'older_latest_symbols':[x['symbol'] for x in older],'no_pit_report_symbols':out['no_pit_report_symbols']},indent=2))

if __name__=='__main__':main()
