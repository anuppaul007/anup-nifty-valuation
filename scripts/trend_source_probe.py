#!/usr/bin/env python3
"""Research-only source probe for the frozen SMA10 trend challenger.

Discovers whether the exact frozen sleeve indices can be retrieved with daily
history. It never substitutes another debt instrument if the required NIFTY
10 YR BENCHMARK G-SEC total-return index is unavailable.
"""
from __future__ import annotations
from datetime import date
from pathlib import Path
import json
import pandas as pd
import update_data as b

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'trend_source_probe.json'
START=date(2000,1,1)


def _parse(rows):
    pts=[]
    for x in rows or []:
        dt=b.pdate(b.pick(x,['Date','DATE','HistoricalDate','Index Date']))
        val=b.fnum(b.pick(x,['Total Returns Index','TRI','Close','CLOSE','Closing Index Value','Index Value','INDEX_VALUE']))
        if dt and val and float(val)>0:pts.append((pd.Timestamp(dt),float(val)))
    if not pts:return None
    s=pd.DataFrame(pts,columns=['date','value']).drop_duplicates('date').set_index('date').value.sort_index()
    return {'rows':int(len(s)),'first':str(s.index.min().date()),'last':str(s.index.max().date()),'first_value':float(s.iloc[0]),'last_value':float(s.iloc[-1])}


def tri(name):
    from jugaad_data.nse import index_tri_raw
    candidates=[(name,name)]
    # Historical API sometimes separates broad category and index name. Keep
    # exact index identity; category aliases do not change the requested index.
    if name=='NIFTY 50':candidates += [('NIFTY 50','NIFTY 50')]
    if name=='NIFTY 10 YR BENCHMARK G-SEC':
        candidates += [
            ('NIFTY 10 YR BENCHMARK G-SEC','NIFTY 10 YR BENCHMARK G-SEC'),
            ('NIFTY FIXED INCOME','NIFTY 10 YR BENCHMARK G-SEC'),
            ('NIFTY FIXED INCOME INDICES','NIFTY 10 YR BENCHMARK G-SEC'),
        ]
    errors=[]
    for family,index in candidates:
        try:
            rows=index_tri_raw(family,index,START,date.today())
            parsed=_parse(rows)
            if parsed:return {'status':'ok','family':family,'index':index,**parsed}
            errors.append(f'{family}: empty')
        except Exception as e:errors.append(f'{family}: {type(e).__name__}: {e}')
    return {'status':'unavailable','index':name,'errors':errors}


def price():
    from jugaad_data.nse import index_raw
    try:return {'status':'ok',**(_parse(index_raw('NIFTY 50',START,date.today())) or {})}
    except Exception as e:return {'status':'unavailable','error':f'{type(e).__name__}: {e}'}


def main():
    out={
      'research_only':True,
      'frozen_policy':'trend-sma10-minus20-v1',
      'nifty50_price':price(),
      'nifty50_tri':tri('NIFTY 50'),
      'debt_tri':tri('NIFTY 10 YR BENCHMARK G-SEC'),
      'substitution_allowed':False,
      'live_allocation_effect':'none',
    }
    OUT.write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(out,indent=2))

if __name__=='__main__':main()
