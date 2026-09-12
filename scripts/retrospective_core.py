#!/usr/bin/env python3
"""Retrospective sensitivity test for the valuation core only.

This is deliberately *not* a parameter-fitting engine and does not alter the
live V3.6 rule. It asks two narrow questions in the common post-31-Mar-2021
NSE valuation methodology era:

1. How sensitive were outcomes to the valuation-to-equity curve slope ``k``?
2. Does the live extreme threshold ``zc=2.5`` drive the model to 0%/100% equity
   too readily compared with wider thresholds such as 3.0, 3.5 and 4.0?

Signals use only completed month-end observations. A month-t allocation is
applied to month t+1 total returns, so no same-month return is used to score its
own signal. This remains retrospective rather than true out-of-sample validation
because the fixed valuation reference constants were not frozen in April 2021.
"""
from __future__ import annotations
from datetime import date
from pathlib import Path
import json, math
import numpy as np
import pandas as pd
import update_data as b
import macro_v3 as m

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'retrospective.json'
START=date(2021,4,1)
CURVES=[.60,.80,1.00,1.15,1.35,1.50]
EXTREMES=[2.5,3.0,3.5,4.0]
LIVE_K=1.35
LIVE_ZC=2.5
C={'peM':22.44,'peS':2.08,'pbM':3.88,'pbS':.45,'roeM':17.36,'roeS':1.92,
   'dyM':1.25,'dyS':.18,'gapM':-2.60,'gapS':.70,'beta':.60}
COST_PER_100_TURNOVER=.001  # 10 bps one-way sensitivity, excluding tax.


def finite(x):
    try:return x is not None and math.isfinite(float(x))
    except (TypeError,ValueError):return False

def clip(x,a,b):return max(a,min(b,float(x)))
def curve(z,k=LIVE_K,zc=LIVE_ZC):
    k=float(k);zc=float(zc)
    if zc<=0:raise ValueError('zc must be positive')
    f=lambda x:100/(1+math.exp(k*x));lo=f(zc);hi=f(-zc)
    return clip((f(z)-lo)/(hi-lo)*100,0,100)

def parse_rows(rows,value_aliases):
    out=[]
    for row in rows or []:
        dt=b.pdate(b.pick(row,['Date','DATE','HistoricalDate','Index Date']))
        val=b.fnum(b.pick(row,value_aliases))
        if dt and dt<=date.today() and finite(val) and val>0:out.append((pd.Timestamp(dt),float(val)))
    if not out:return pd.Series(dtype=float)
    return pd.DataFrame(out,columns=['date','value']).drop_duplicates('date').set_index('date').value.sort_index()

def month_end(s):
    if s.empty:return s
    s=s[s.index<pd.Timestamp(date.today().replace(day=1))]
    return s.groupby(s.index.to_period('M')).last()

def fetch_panel():
    from jugaad_data.nse import index_pe_raw,index_tri_raw,index_raw
    end=date.today();ratios=index_pe_raw('NIFTY 50',START,end)
    tri=index_tri_raw('NIFTY 50','NIFTY 50',START,end)
    debt=index_raw('NIFTY 10 YR BENCHMARK G-SEC',START,end)

    rr=[]
    for x in ratios or []:
        dt=b.pdate(b.pick(x,['Date','DATE','HistoricalDate']))
        pe=b.fnum(b.pick(x,['P/E','PE','pe']));pb=b.fnum(b.pick(x,['P/B','PB','pb']));dy=b.fnum(b.pick(x,['Div Yield %','Div Yield','Dividend Yield','DY','divYield']))
        if dt and dt<=end and all(finite(v) and v>0 for v in (pe,pb,dy)):rr.append((pd.Timestamp(dt),float(pe),float(pb),float(dy)))
    if len(rr)<100:raise RuntimeError(f'Insufficient NIFTY valuation history: {len(rr)} rows')
    rdf=pd.DataFrame(rr,columns=['date','pe','pb','dy']).drop_duplicates('date').set_index('date').sort_index()
    current_month=pd.Timestamp(date.today().replace(day=1));rdf=rdf[rdf.index<current_month].groupby(rdf[rdf.index<current_month].index.to_period('M')).last()

    eq=month_end(parse_rows(tri,['Total Returns Index','TRI','Close','CLOSE','Closing Index Value','Close Price','Index Value']))
    db=month_end(parse_rows(debt,['Close','CLOSE','Closing Index Value','Close Price','Index Value']))
    if len(eq)<24:raise RuntimeError(f'Insufficient NIFTY 50 TRI history: {len(eq)} months')
    if len(db)<24:raise RuntimeError(f'Insufficient NIFTY 10Y G-Sec history: {len(db)} months')

    y=m.oecd_india_10y().copy();ys=y.set_index(pd.to_datetime(y.date).dt.to_period('M')).value.astype(float)
    panel=rdf.join(eq.rename('equity_tri'),how='inner').join(db.rename('debt_tri'),how='inner').join(ys.rename('gsec10'),how='inner')
    panel=panel.replace([np.inf,-np.inf],np.nan).dropna().sort_index()
    if len(panel)<36:raise RuntimeError(f'Only {len(panel)} complete comparable months after source alignment')
    return panel

def valuation_z(row):
    pe,pb,dy,gsec=map(float,(row.pe,row.pb,row.dy,row.gsec10));roe=100*pb/pe;gap=100/pe-gsec
    lenses=[((pe-C['peM'])/C['peS'],30),((pb-C['pbM'])/C['pbS']-C['beta']*(roe-C['roeM'])/C['roeS'],25),(-(gap-C['gapM'])/C['gapS'],30),(-(dy-C['dyM'])/C['dyS'],10)]
    return sum(v*w for v,w in lenses)/sum(w for _,w in lenses)

def max_drawdown(returns):
    wealth=np.cumprod(1+np.asarray(returns,float));peak=np.maximum.accumulate(wealth);dd=wealth/peak-1
    return float(np.min(dd)) if len(dd) else None

def stats(returns,weights=None,costed=False):
    r=np.asarray(returns,float);n=len(r)
    if not n:return {}
    wealth=float(np.prod(1+r));years=n/12;cagr=wealth**(1/years)-1 if wealth>0 and years>0 else None
    vol=float(np.std(r,ddof=1)*math.sqrt(12)) if n>1 else None;dd=max_drawdown(r)
    downside=np.minimum(r,0);downvol=float(np.sqrt(np.mean(downside**2))*math.sqrt(12)) if n else None
    turnover=float(np.sum(np.abs(np.diff(weights)))/years) if weights is not None and len(weights)>1 else None
    return {'months':n,'cagr_pct':100*cagr if finite(cagr) else None,'annual_vol_pct':100*vol if finite(vol) else None,
            'max_drawdown_pct':100*dd if finite(dd) else None,'sortino_0':(cagr/downvol if finite(cagr) and finite(downvol) and downvol>0 else None),
            'calmar':(cagr/abs(dd) if finite(cagr) and finite(dd) and dd<0 else None),'ending_wealth_from_100':100*wealth,
            'worst_month_pct':100*float(np.min(r)),'annual_turnover_x':turnover,'costed_10bp_turnover':bool(costed)}

def strategy_returns(panel,k=LIVE_K,zc=LIVE_ZC):
    z=panel.apply(valuation_z,axis=1);w=z.map(lambda x:curve(float(x),k,zc)/100)
    eq=panel.equity_tri.pct_change().shift(-1);db=panel.debt_tri.pct_change().shift(-1)
    frame=pd.DataFrame({'w':w,'eq':eq,'db':db}).dropna()
    gross=frame['w']*frame['eq']+(1-frame['w'])*frame['db']
    turnover=frame['w'].diff().abs().fillna(0);net=gross-COST_PER_100_TURNOVER*turnover
    return frame,gross,net,z.loc[frame.index]

def candidate_stats(panel,k,zc):
    frame,gross,net,_=strategy_returns(panel,k,zc);weights=frame['w'].to_numpy()
    return {'gross':stats(gross.to_numpy(),weights,False),'net_10bp_turnover':stats(net.to_numpy(),weights,True),
            'average_equity_pct':100*float(frame['w'].mean()),'min_equity_pct':100*float(frame['w'].min()),'max_equity_pct':100*float(frame['w'].max())}

def fixed_returns(panel,w):
    eq=panel.equity_tri.pct_change().shift(-1);db=panel.debt_tri.pct_change().shift(-1)
    return (w*eq+(1-w)*db).dropna()

def grid_key(k,zc):return f'k={float(k):.2f}|zc={float(zc):.1f}'

def main():
    try:
        panel=fetch_panel();records=[]
        slope_candidates={str(k):candidate_stats(panel,k,LIVE_ZC) for k in CURVES}
        endpoint_candidates={str(zc):candidate_stats(panel,LIVE_K,zc) for zc in EXTREMES}
        grid_candidates={grid_key(k,zc):candidate_stats(panel,k,zc) for zc in EXTREMES for k in CURVES}
        baselines={name:stats(fixed_returns(panel,w).to_numpy(),None,False) for name,w in [('60_40',.60),('70_30',.70),('100_equity',1.0)]}
        zall=panel.apply(valuation_z,axis=1);latest_z=float(zall.iloc[-1])
        for month,row in panel.iterrows():
            records.append({'month':str(month),'pe':float(row.pe),'pb':float(row.pb),'dividend_yield':float(row.dy),'gsec10':float(row.gsec10),
                            'valuation_z':float(zall.loc[month]),'equity_tri':float(row.equity_tri),'debt_tri':float(row.debt_tri)})
        best_cagr=max(grid_candidates,key=lambda key:grid_candidates[key]['net_10bp_turnover']['cagr_pct'])
        best_calmar=max(grid_candidates,key=lambda key:grid_candidates[key]['net_10bp_turnover']['calmar'])
        out={'schema_version':2,'status':'complete','model_version':'3.6','study':'valuation-core retrospective slope-and-extreme sensitivity',
             'methodology':{'start':'2021-04','end_completed_month':str(panel.index[-1]),'signal_rule':'month-end valuation signal applied to next completed month return',
                            'equity_benchmark':'NIFTY 50 Total Return Index','debt_benchmark':'NIFTY 10 YR BENCHMARK G-SEC total-return index',
                            'transaction_cost_sensitivity':'10 bps per 100% one-way allocation turnover; taxes excluded',
                            'important_limit':'Retrospective sensitivity only. Fixed reference constants were not proven frozen at the start date; grid winners are not eligible for automatic adoption.'},
             'live_parameters':{'curve_slope_k':LIVE_K,'extreme_threshold_zc':LIVE_ZC},'comparable_months':int(len(panel)),'performance_months':int(len(panel)-1),
             'latest_completed_signal':{'month':str(panel.index[-1]),'valuation_z':latest_z,
                'candidate_core_equity_by_slope_pct':{str(k):curve(latest_z,k,LIVE_ZC) for k in CURVES},
                'candidate_core_equity_by_extreme_pct':{str(zc):curve(latest_z,LIVE_K,zc) for zc in EXTREMES}},
             'candidate_curve_slopes':CURVES,'candidate_extreme_thresholds':EXTREMES,
             'candidates':slope_candidates,'endpoint_candidates':endpoint_candidates,'grid_candidates':grid_candidates,'baselines':baselines,
             'best_grid_net_cagr':best_cagr,'best_grid_net_calmar':best_calmar,'records':records}
    except Exception as e:
        out={'schema_version':2,'status':'unavailable','model_version':'3.6','study':'valuation-core retrospective slope-and-extreme sensitivity','error':f'{type(e).__name__}: {e}'}
    tmp=OUT.with_suffix('.tmp');tmp.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8');tmp.replace(OUT)
    print(json.dumps({k:out.get(k) for k in ('status','comparable_months','performance_months','best_grid_net_cagr','best_grid_net_calmar','error') if k in out}))
if __name__=='__main__':main()
