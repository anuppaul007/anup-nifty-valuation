#!/usr/bin/env python3
"""Refresh dated source data. Missing sources are explicit and never neutral."""
from datetime import date,timedelta,datetime,timezone
from io import StringIO
from pathlib import Path
import json,re
import numpy as np
import pandas as pd
from lxml import html
import http_client as requests
import update_data as b
import macro_v3 as m
import domestic_macro as dm
import valuation_diagnostics as vd
import data_quality as dq

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'latest.json'
# V3.6 true macro plan. Relative EM valuation remains a diagnostic valuation
# cross-check, not a macro block. The four macro blocks sum to 100%.
m.BLOCKS.clear();m.BLOCKS.update({'global_liquidity':.30,'india_external_carry':.25,'india_domestic':.25,'china_industrial':.20})
coverage_adjust_macro=m.coverage_adjust_macro


def parse_rbi_yield(text):
    page=' '.join(html.fromstring(text).text_content().split())
    section=re.search(r'Government\s+Securities\s+Market(.*?)Capital\s+Market',page,re.I)
    if not section:raise RuntimeError('RBI government-securities section not found')
    section=section.group(1);dates=set(re.findall(r'as on\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',section,re.I))
    if len(dates)!=1:raise RuntimeError('RBI bond observation date is missing or ambiguous')
    dt=pd.to_datetime(dates.pop()).date();bonds=[]
    for coupon,year,yield_ in re.findall(r'(\d+(?:\.\d+)?)\s*%\s*GS\s*(20\d{2})\s*:?\s*(\d+(?:\.\d+)?)\s*%',section,re.I):
        distance=abs(int(year)-dt.year-10)
        if distance<=1 and 3<float(yield_)<15:bonds.append((distance,float(yield_),f'{coupon}% GS {year}'))
    if not bonds:raise RuntimeError('RBI approximately 10-year bond not found')
    closest=min(x[0] for x in bonds);matches=[x for x in bonds if x[0]==closest]
    if len(matches)!=1:raise RuntimeError('RBI 10-year bond selection is ambiguous')
    _,value,security=matches[0]
    return value,{'asof':dt.isoformat(),'source_url':'https://www.rbi.org.in/','source':'RBI dated government bond near 10 years','security':security,'status':'live','max_age_days':7}


def india_yield(old):
    def rbi():
        response=requests.get('https://www.rbi.org.in/',headers=m.UA);response.raise_for_status();value,meta=parse_rbi_yield(response.text)
        if not m.fresh(meta['asof'],7):raise RuntimeError('RBI bond observation is stale')
        return value,meta
    found=m.safe('RBI dated yield',rbi)
    if found:return found
    url='https://www.fbil.org.in/'
    def fbil():
        for t in pd.read_html(StringIO(requests.get(url,headers=m.UA).text)):
            cols=[' '.join(map(str,c)) if isinstance(c,tuple) else str(c) for c in t.columns];ci={k:next((i for i,c in enumerate(cols) if k in c.lower()),None) for k in ('tenor','rate','date')}
            if any(v is None for v in ci.values()):continue
            for _,row in t.iterrows():
                if str(row.iloc[ci['tenor']]).upper().replace(' ','') not in ('10YR','10Y','10YEARS'):continue
                val=b.fnum(row.iloc[ci['rate']]);dt=b.pdate(row.iloc[ci['date']])
                if val is not None and 3<val<15 and dt and m.fresh(dt.isoformat(),7):return val,{'asof':dt.isoformat(),'source_url':url,'source':'FBIL dated 10Y par yield','status':'live','max_age_days':7}
        raise RuntimeError('A dated India 10Y row was not found')
    found=m.safe('FBIL dated yield',fbil)
    if found:return found
    def monthly():
        df=m.oecd_india_10y();dt=df.attrs['asof'];v=float(df.value.iloc[-1])
        if not 3<v<15 or not m.fresh(dt,100):raise RuntimeError('OECD India monthly long-term yield is stale')
        return v,{'asof':dt,'source_url':df.attrs['source'],'source':'OECD monthly India long-term government bond yield','status':'lagged','max_age_days':100}
    found=m.safe('OECD India monthly yield',monthly)
    if found:return found
    meta=(old.get('nifty') or {}).get('gsec_meta') or {};value=(old.get('nifty') or {}).get('gsec10')
    if m.finite(value) and meta.get('status')!='excluded' and m.fresh(meta.get('asof'),meta.get('max_age_days',7)):return float(value),dict(meta,status='cached')
    return value,{'asof':meta.get('asof'),'status':'excluded','source':'India 10Y unavailable or undated','source_url':meta.get('source_url'),'max_age_days':7}


def unavailable_macro(old,reason):
    mac=dict(old.get('macro') or {});mac.update(score=None,active_block_weight=0,blocks={k:None for k in m.BLOCKS},factor_coverage={k:0 for k in m.BLOCKS},build_error=reason)
    mac['factors']={k:dict(v,score=None,status='cached') for k,v in (mac.get('factors') or {}).items()}
    return m.coverage_adjust_macro(mac)


def attach_domestic(mac,old):
    prior=(old.get('macro') or {}).get('domestic') or {}
    dom=m.safe('India domestic macro',lambda:dm.build(prior))
    if dom is None:dom={'score':None,'coverage':0.0,'status':'unavailable','factors':{},'method':'economic-anchor-v1'}
    mac['domestic']=dom;mac.setdefault('blocks',{})['india_domestic']=dom.get('score');mac.setdefault('factor_coverage',{})['india_domestic']=float(dom.get('coverage') or 0)
    return m.coverage_adjust_macro(mac)


def nifty_trend():
    """Frozen SMA10 live risk-control input using completed monthly NIFTY price closes only."""
    policy='trend-sma10-minus20-v1'
    try:
        from jugaad_data.nse import index_raw
        end=date.today();start=end-timedelta(days=600)
        rows=index_raw('NIFTY 50',start,end)
        pts=[]
        for x in rows or []:
            dt=b.pdate(b.pick(x,['Date','DATE','HistoricalDate','Index Date']))
            close=b.fnum(b.pick(x,['Close','CLOSE','Closing Index Value','Close Price','Index Value']))
            if dt and dt<=end and close is not None and close>0:pts.append((pd.Timestamp(dt),float(close)))
        if len(pts)<200:raise RuntimeError(f'insufficient NIFTY price observations: {len(pts)}')
        s=pd.DataFrame(pts,columns=['date','close']).drop_duplicates('date').set_index('date').close.sort_index()
        current=pd.Period(end,freq='M')
        completed=s[s.index.to_period('M')<current]
        monthly=completed.groupby(completed.index.to_period('M')).last().sort_index()
        if len(monthly)<10:raise RuntimeError(f'only {len(monthly)} completed monthly closes')
        last10=monthly.tail(10);month=last10.index[-1];close=float(last10.iloc[-1]);sma=float(last10.mean())
        month_dates=completed[completed.index.to_period('M')==month]
        if month_dates.empty:raise RuntimeError('completed-month observation date unavailable')
        asof=str(month_dates.index[-1].date());risk_off=bool(close<sma)
        return {'status':'live','policy_id':policy,'source':'Nifty Indices / NSE NIFTY 50 price index','source_url':'https://www.niftyindices.com/reports/historical-data','asof':asof,'completed_month':str(month),'completed_month_close':close,'sma10':sma,'distance_to_sma10_pct':100*(close/sma-1),'lookback_months':10,'risk_off':risk_off,'risk_off_adjustment_pp':-20 if risk_off else 0,'rule':'previous completed-month close strictly below mean of latest 10 consecutive completed monthly closes'}
    except Exception as e:
        return {'status':'unavailable','policy_id':policy,'asof':None,'completed_month':None,'completed_month_close':None,'sma10':None,'lookback_months':10,'risk_off':None,'risk_off_adjustment_pp':None,'error':f'{type(e).__name__}: {e}'}


def main():
    try:old=json.loads(OUT.read_text())
    except (OSError,ValueError):old={}
    n=b.fetch_nifty();g10,gmeta=india_yield(old);trend=nifty_trend();latest=n['latest'];latest.update(gsec10=g10,gsec_meta=gmeta)
    if any(not m.finite(latest.get(k)) or latest[k]<=0 for k in ['level','pe','pb','div_yield']):raise RuntimeError('Mandatory NIFTY input validation failed; retaining saved data')
    if not m.fresh(latest.get('date'),7):raise RuntimeError('Mandatory NIFTY observation date is stale')
    breaks=dq.ratio_breaks(n['history'])
    if any(e['status']=='unresolved_ratio_break' for e in breaks):
        raise RuntimeError('Unresolved NIFTY ratio discontinuity; retaining prior packet: '+json.dumps(breaks))
    transitions,changed=dq.security_transition(old,gmeta)
    gmeta['security_changed']=changed
    gmeta['last_transition']=transitions[-1] if transitions else None
    try:
        mac,cal=m.build(g10,latest,n['history'],old,gmeta);mac=attach_domestic(mac,old)
    except Exception as e:
        mac=unavailable_macro(old,str(e));cal=dict(old.get('calibration') or {})
    cal['india_yield_transitions']=transitions
    valuation_diag=vd.build(n['history'],latest)
    valuation_diag['ratio_breaks']=breaks
    coverage=mac['active_block_weight'];vf=(mac.get('factors') or {}).get('vix') or {};confidence=None
    if vf.get('status')=='live' and m.finite(vf.get('value')):
        stress=float(np.clip(1-max(0,vf['value']-18)/40,.35,1));confidence=stress*(.65+.35*coverage)
    out={'schema_version':4,'model_version':'3.12-evidence-first-1','generated_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'macro_stale':coverage==0,'macro_partial':coverage<.999,'nifty':latest,'earnings':n['earnings'],'macro':mac,'trend':trend,'confidence':confidence,'valuation_diagnostics':valuation_diag,'history':n['history'],'calibration':cal,'sources':[
        {'name':'Nifty Indices / NSE','role':'NIFTY index and ratio history; EPS is an index-implied proxy; completed monthly price closes drive the live SMA10 crash guard','url':'https://www.niftyindices.com/reports/historical-data'},
        {'name':gmeta['source'],'role':'Current India ~10Y yield; its own observation date determines eligibility','url':gmeta.get('source_url')},
        {'name':'U.S. Treasury / Federal Reserve / CBOE','role':'Dated real/nominal yields, broad USD, Fed balance sheet and VIX; V3.12 displays these as context and evaluates a shadow macro challenger rather than using them in the live allocation'},
        {'name':'BIS Statistics API','role':'India broad REER and monthly USD/INR history from official SDMX feeds','url':'https://data.bis.org/'},
        {'name':'OECD Data Explorer','role':'Monthly India long-term government bond history used to standardise India-US carry','url':'https://data-explorer.oecd.org/'},
        {'name':'MoSPI / NSO via Press Information Bureau','role':'Official All-India CPI inflation and Index of Industrial Production releases; newest URL is discovered and prior verified URL is carried forward','url':dm.PIB_ALL},
        {'name':'Reserve Bank of India','role':'Current policy repo rate and dated government-security yield','url':dm.RBI},
        {'name':'Yahoo Finance Brent futures','role':'Brent 63-trading-observation momentum; contract-roll effects are possible'},
        {'name':'STOXX EM ex India Universal Large Cap','role':'Relative valuation diagnostic only; not counted as a macro block','url':m.STOXX_URL},
        {'name':'NBS China','role':'Official manufacturing PMI and new orders','url':(mac.get('china_pmi') or {}).get('source_url')}
    ]}
    tmp=OUT.with_suffix('.tmp');tmp.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8');tmp.replace(OUT)
    print(json.dumps({'nifty_asof':latest['date'],'gsec_status':gmeta['status'],'macro_score':mac['score'],'coverage':coverage,'trend_status':trend.get('status'),'trend_risk_off':trend.get('risk_off'),'domestic_status':(mac.get('domestic') or {}).get('status'),'valuation_cheapness':valuation_diag.get('composite_cheapness'),'valuation_months':valuation_diag.get('months'),'version':'3.12-evidence-first-1'}))
if __name__=='__main__':main()
