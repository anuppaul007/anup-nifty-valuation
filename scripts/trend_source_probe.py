#!/usr/bin/env python3
"""Research-only source probe for the frozen SMA10 trend challenger.

NSE Indices states that fixed-income indices are Total Return except the
separately named Nifty 10 yr Benchmark G-Sec (Clean Price). Therefore the
frozen debt sleeve is retrieved as the historical close of the exact
`NIFTY 10 YR BENCHMARK G-SEC` index. No substitute debt index is permitted.
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


def equity_tri():
    from jugaad_data.nse import index_tri_raw
    try:return {'status':'ok',**(_parse(index_tri_raw('NIFTY 50','NIFTY 50',START,date.today())) or {})}
    except Exception as e:return {'status':'unavailable','error':f'{type(e).__name__}: {e}'}


def index_close(name):
    from jugaad_data.nse import index_raw
    try:return {'status':'ok',**(_parse(index_raw(name,START,date.today())) or {})}
    except Exception as e:return {'status':'unavailable','error':f'{type(e).__name__}: {e}'}


def main():
    out={
      'research_only':True,
      'frozen_policy':'trend-sma10-minus20-v1',
      'nifty50_price':index_close('NIFTY 50'),
      'nifty50_tri':equity_tri(),
      'debt_tri':index_close('NIFTY 10 YR BENCHMARK G-SEC'),
      'debt_identity_note':'NSE Indices fixed-income index close is total return; Clean Price is a separately named excluded index.',
      'substitution_allowed':False,
      'live_allocation_effect':'none',
    }
    OUT.write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(out,indent=2))

if __name__=='__main__':main()
