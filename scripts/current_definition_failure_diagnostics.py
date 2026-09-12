#!/usr/bin/env python3
"""Compact diagnostics for anchor-validation failures. Research only."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import json
import pandas as pd

import current_definition_anchor_validation as a

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'current_definition_failure_diagnostics.json'
SYMS=['RELIANCE','HDFCBANK','ASIANPAINT','INFY','SBIN','HDFCLIFE','LTIM','NESTLEIND','TATAMOTORS','INDUSINDBK']


def row_meta(r):
    return {k:r.get(k) for k in ('symbol','companyName','fromDate','toDate','filingDate','broadCastDate','consolidated','cumulative','period','financialYear','relatingTo','xbrl') if k in r}


def profitish(url):
    try:
        root=a.xbrl_root(url); fs=a.facts(root)
        hits=[]
        for f in fs:
            n=f['name'].lower()
            if any(k in n for k in ('profit','loss','earnings','pat','incomeattributable')):
                hits.append({'name':f['name'],'value':f['value'],'context':f['context'],'period':f['period']})
        # unique compact list preserving first occurrence per tag/context/period
        seen=set();out=[]
        for h in hits:
            key=(h['name'],h['context'],str(h['period']))
            if key in seen:continue
            seen.add(key);out.append(h)
            if len(out)>=80:break
        return {'status':'ok','hits':out}
    except Exception as e:
        return {'status':'unavailable','error':f'{type(e).__name__}: {e}'}


def diagnose(sym):
    q=a.financial_rows(sym,'Quarterly')
    grouped={}
    for r in q:
        if r['_to'] is not None and r['_to'].date()<=a.SIGNAL.date():grouped.setdefault(str(r['_to'].date()),[]).append(r)
    dates=sorted(grouped.keys(),reverse=True)[:8]
    groups=[]
    for d in dates:
        rows=grouped[d]
        chosen=a.choose_basis(rows)
        item={'toDate':d,'row_count':len(rows),'rows':[row_meta(r) for r in rows[:6]],'chosen':row_meta(chosen) if chosen else None}
        if chosen:
            item['duration_days']=(chosen['_to']-chosen['_from']).days+1 if chosen.get('_to') is not None and chosen.get('_from') is not None else None
            item['profitish']=profitish(chosen['xbrl'])
        groups.append(item)
    return {'symbol':sym,'eligible_quarterly_rows':len(q),'groups':groups}


def main():
    out={'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'research_only':True,'live_model_changed':False,'symbols':[]}
    for s in SYMS:
        try:out['symbols'].append(diagnose(s))
        except Exception as e:out['symbols'].append({'symbol':s,'error':f'{type(e).__name__}: {e}'})
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    print(json.dumps({s.get('symbol'): {'rows':s.get('eligible_quarterly_rows'),'groups':len(s.get('groups',[])),'error':s.get('error')} for s in out['symbols']},indent=2))

if __name__=='__main__':main()
