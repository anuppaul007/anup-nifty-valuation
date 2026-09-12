#!/usr/bin/env python3
"""Check whether special companies exist in NSE historical results without symbol filter."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json
import current_definition_anchor_validation_v3 as v3

a=v3.a
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'current_definition_unfiltered_results_probe.json'
TARGET={'HDFCLIFE','LTIM','NESTLEIND','SBILIFE','TATAMOTORS','INDUSINDBK'}
WINDOWS=[('01-04-2022','30-06-2022'),('01-07-2022','30-09-2022'),('01-10-2022','31-12-2022'),('01-01-2023','31-03-2023'),('01-04-2023','30-06-2023'),('01-07-2023','29-09-2023')]

def main():
    hits={s:[] for s in TARGET};stats=[]
    for fr,to in WINDOWS:
        try:
            d=a.get_json('https://www.nseindia.com/api/corporates-financial-results',{'index':'equities','from_date':fr,'to_date':to})
            rows=d if isinstance(d,list) else d.get('data',[]) if isinstance(d,dict) else []
            stats.append({'from':fr,'to':to,'count':len(rows)})
            for r in rows:
                sym=str(r.get('symbol') or '').upper().strip()
                if sym in TARGET:
                    hits[sym].append({k:r.get(k) for k in ('symbol','companyName','fromDate','toDate','filingDate','broadCastDate','consolidated','cumulative','period','financialYear','relatingTo','xbrl','resultDetailedDataLink')})
        except Exception as e:stats.append({'from':fr,'to':to,'error':f'{type(e).__name__}: {e}'})
    out={'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'research_only':True,'live_model_changed':False,'window_stats':stats,'hits':hits}
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    print(json.dumps({'windows':stats,'hit_counts':{s:len(v) for s,v in hits.items()}},indent=2))
if __name__=='__main__':main()
