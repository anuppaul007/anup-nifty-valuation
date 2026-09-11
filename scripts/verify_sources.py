"""Native integration verification of proposed primary-source adapters."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,date
from pathlib import Path
import json
import pandas as pd
import macro_sources as s
import update_data as b

def load(item):
    key,fn=item
    try:
        x=fn()
        if isinstance(x,pd.DataFrame):x={'source':x.attrs.get('source'),'asof':x.attrs.get('asof'),'history':s.records(x)}
        return key,{'ok':True,'data':x}
    except Exception as e:return key,{'ok':False,'error':f'{type(e).__name__}: {e}'}

def nifty_monthly():
    from jugaad_data.nse import index_raw,index_pe_raw
    start=date(2021,4,1);end=date.today()
    prices=index_raw('NIFTY 50',start,end);ratios=index_pe_raw('NIFTY 50',start,end)
    pp={str(b.pdate(b.pick(x,['Date','DATE','HistoricalDate']))):b.fnum(b.pick(x,['Close','CLOSE','Closing Index Value','Close Price'])) for x in prices}
    points=[]
    for x in ratios:
        dt=b.pdate(b.pick(x,['Date','DATE','HistoricalDate']));v=pp.get(str(dt))
        pe=b.fnum(b.pick(x,['P/E','PE','pe']));pb=b.fnum(b.pick(x,['P/B','PB','pb']));dy=b.fnum(b.pick(x,['Div Yield %','Div Yield','Dividend Yield','DY','divYield']))
        if dt and v and pe and pb and dy is not None:points.append({'date':str(dt),'level':v,'pe':pe,'pb':pb,'dy':dy,'eps':v/pe})
    t=pd.DataFrame(points).sort_values('date').drop_duplicates('date')
    monthly=t.groupby(t.date.str[:7]).tail(1)
    return {'monthly':monthly.to_dict(orient='records'),'daily':t.to_dict(orient='records')}

def main():
    tasks={'india_reer':lambda:s.bis_series('WS_EER','M.R.B.IN'),'india_cpi':lambda:s.bis_series('WS_LONG_CPI','M.IN'),'india_policy':lambda:s.bis_series('WS_CBPOL','M.IN'),'rbi_financials':s.rbi_financials,'nifty':nifty_monthly}
    with ThreadPoolExecutor(max_workers=5) as pool:result=dict(pool.map(load,tasks.items()))
    out={'retrieved_at':datetime.now(timezone.utc).isoformat(),'sources':result}
    path=Path(__file__).resolve().parents[1]/'research'/'sources.json';path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out,indent=2,allow_nan=False))
    print(json.dumps({k:{'ok':v['ok'],'error':v.get('error'),'asof':v.get('data',{}).get('asof'),'observations':len(v.get('data',{}).get('history',[]))} for k,v in result.items()}))
if __name__=='__main__':main()
