#!/usr/bin/env python3
"""Diagnostics for the 12 residual Sep-2023 anchor constituents. Research only."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json

import current_definition_anchor_validation_v3 as v3

a=v3.a
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'current_definition_special_diagnostics.json'
BANKS=['AXISBANK','HDFCBANK','ICICIBANK','KOTAKBANK','SBIN']
SPECIAL=['HDFCLIFE','LTIM','NESTLEIND','SBILIFE','TATAMOTORS','INDUSINDBK']


def raw_rows(sym,period):
    try:
        d=a.get_json('https://www.nseindia.com/api/corporates-financial-results',{'index':'equities','symbol':sym,'period':period})
        rows=d if isinstance(d,list) else d.get('data',[]) if isinstance(d,dict) else []
        keep=[]
        for r in rows[:40]:
            keep.append({k:r.get(k) for k in ('symbol','companyName','fromDate','toDate','filingDate','broadCastDate','consolidated','cumulative','period','financialYear','relatingTo','xbrl','resultDetailedDataLink','attachment','attchmntFile') if k in r})
        return {'status':'ok','count':len(rows),'keys':sorted(rows[0].keys()) if rows else [],'rows':keep}
    except Exception as e:return {'status':'unavailable','error':f'{type(e).__name__}: {e}'}


def capish(sym,period):
    try:
        rows=a.financial_rows(sym,period)
        row=a.choose_basis(rows)
        if not row:return {'status':'no_eligible_xbrl'}
        root=a.xbrl_root(row['xbrl']); fs=a.facts(root);hits=[]
        for f in fs:
            n=f['name'].lower()
            if any(k in n for k in ('capital','facevalue','sharecapital','numberofshare','equityshare','paidup','reserves','networth','otherequity','equityattributable')):
                hits.append({'name':f['name'],'value':f['value'],'context':f['context'],'period':f['period']})
        seen=set();out=[]
        for h in hits:
            key=(h['name'],h['context'],str(h['period']),h['value'])
            if key not in seen:seen.add(key);out.append(h)
            if len(out)>=120:break
        return {'status':'ok','row':{k:row.get(k) for k in ('fromDate','toDate','filingDate','consolidated','cumulative','xbrl')},'hits':out}
    except Exception as e:return {'status':'unavailable','error':f'{type(e).__name__}: {e}'}


def main():
    out={'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'research_only':True,'live_model_changed':False,'banks':{},'special':{}}
    for s in BANKS:
        out['banks'][s]={'quarter_capish':capish(s,'Quarterly'),'annual_capish':capish(s,'Annual')}
    for s in SPECIAL:
        out['special'][s]={p:raw_rows(s,p) for p in ('Quarterly','Half Yearly','Annual')}
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    print(json.dumps({'banks':{k:v['quarter_capish'].get('status') for k,v in out['banks'].items()},'special':{k:{p:v[p].get('count') for p in ('Quarterly','Half Yearly','Annual')} for k,v in out['special'].items()}},indent=2))

if __name__=='__main__':main()
