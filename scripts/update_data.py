#!/usr/bin/env python3
"""Update data/latest.json for Anup Nifty Valuation V2.1.

Architecture
------------
1) Fundamental NIFTY valuation remains the core allocation engine.
2) Earnings cycle is a bounded overlay.
3) Global/India macro is a bounded overlay and is damped to zero at valuation extremes.
4) Stress variables (especially VIX) reduce confidence/deployment speed instead of redefining fair value.

Automatic public feeds
----------------------
- NIFTY ratios/history: Nifty Indices/NSE via jugaad-data.
- India 10Y: FBIL daily par-yield when parseable; FRED/OECD monthly fallback.
- FRED/BIS/OECD: US real/nominal 10Y, broad USD, Brent, Fed assets, VIX,
  India REER, USD/INR spot, China leading indicator and China credit/GDP.

Two desirable metrics are deliberately optional until a sufficiently robust unattended public feed is available:
- USD/INR forward premium (RBI WSS/FBIL publishes it, but the archive endpoint is brittle).
- MSCI EM ex-India valuation premium (MSCI publishes the benchmark, but a stable free machine feed is not guaranteed).
Missing optional factors reduce macro coverage/confidence; they never silently receive a neutral score.
"""
from __future__ import annotations
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
from io import StringIO
import json, math, re, sys
import numpy as np
import pandas as pd
import http_client as requests

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'latest.json'
UA={'User-Agent':'Mozilla/5.0 (compatible; AnupNiftyValuation/2.1; personal research dashboard)'}


def pick(d, aliases):
    if not isinstance(d,dict): return None
    norm={re.sub(r'[^a-z0-9]','',str(k).lower()):v for k,v in d.items()}
    for a in aliases:
        k=re.sub(r'[^a-z0-9]','',a.lower())
        if k in norm and norm[k] not in ('',None,'-'):
            return norm[k]
    return None

def fnum(x):
    if x is None: return None
    if isinstance(x,(int,float,np.number)):
        return float(x) if math.isfinite(float(x)) else None
    s=str(x).replace(',','').replace('%','').strip()
    try:
        v=float(s); return v if math.isfinite(v) else None
    except Exception:
        return None

def pdate(x):
    if x is None: return None
    s=str(x).strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}',s):
        try:return date.fromisoformat(s[:10])
        except ValueError:return None
    for dayfirst in (True,False):
        try:
            t=pd.to_datetime(s,dayfirst=dayfirst,errors='raise')
            return t.date()
        except Exception:
            pass
    return None

def fred(series):
    url=f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}'
    r=requests.get(url,headers=UA,timeout=30); r.raise_for_status()
    df=pd.read_csv(StringIO(r.text))
    df.columns=['date','value']
    df['date']=pd.to_datetime(df['date'],errors='coerce')
    df['value']=pd.to_numeric(df['value'],errors='coerce')
    return df.dropna().sort_values('date').reset_index(drop=True)

def robust_z(series, floor=1e-9, max_obs=1260):
    s=pd.Series(series)
    if s.empty or pd.isna(s.iloc[-1]):return None
    s=s.dropna()
    if len(s)<13: return None
    look=s.iloc[:-1].tail(max_obs)
    mu=float(look.mean()); sd=float(look.std(ddof=0))
    if not math.isfinite(sd) or sd<floor: return None
    return float(np.clip((float(s.iloc[-1])-mu)/sd,-3,3))

def pct_change_obs(df, lag):
    s=df.set_index('date')['value'].sort_index()
    if len(s)<=lag: return None, pd.Series(dtype=float)
    ch=100*(s/s.shift(lag)-1)
    q=ch.dropna()
    return (float(q.iloc[-1]) if len(q) else None), q

def directional_score(factors):
    """Weighted z-score, renormalised only across actually available factors.

    Each factor dict: key,label,value,z,weight,sign where sign=+1 means high z is supportive.
    Returns tanh-compressed score [-1,1] plus coverage ratio.
    """
    total=sum(float(x['weight']) for x in factors)
    avail=[x for x in factors if x.get('z') is not None and math.isfinite(float(x['z']))]
    used=sum(float(x['weight']) for x in avail)
    if not avail or total<=0 or used<=0:
        return 0.0,0.0
    raw=sum(float(x['weight'])*float(x['sign'])*float(x['z']) for x in avail)/used
    return float(np.tanh(raw/1.5)), float(used/total)


def fetch_nifty():
    from jugaad_data.nse import index_raw, index_pe_raw
    end=date.today(); start=date(2021,5,1)
    ratio=index_pe_raw('NIFTY 50',start,end)
    price=index_raw('NIFTY 50',start,end)
    if not ratio or not price: raise RuntimeError('Nifty Indices returned no data')
    rr=[]
    for x in ratio:
        dt=pdate(pick(x,['Date','DATE','HistoricalDate']))
        pe=fnum(pick(x,['P/E','PE','pe']))
        pb=fnum(pick(x,['P/B','PB','pb']))
        dy=fnum(pick(x,['Div Yield %','Div Yield','Dividend Yield','DY','divYield']))
        if dt and dt<=end and pe and pb and pe>0 and pb>0: rr.append({'date':dt,'pe':pe,'pb':pb,'dy':dy})
    pp=[]
    for x in price:
        dt=pdate(pick(x,['Date','DATE','HistoricalDate']))
        close=fnum(pick(x,['Close','CLOSE','Closing Index Value','Close Price']))
        if dt and dt<=end and close and close>0: pp.append({'date':dt,'level':close})
    if len(rr)<100 or len(pp)<100: raise RuntimeError(f'Parsed too little NIFTY data: ratios={len(rr)}, prices={len(pp)}')
    rdf=pd.DataFrame(rr).drop_duplicates('date').set_index('date').sort_index()
    pdf=pd.DataFrame(pp).drop_duplicates('date').set_index('date').sort_index()
    d=rdf.join(pdf,how='inner').dropna(subset=['pe','pb','level'])
    if len(d)<100: raise RuntimeError('Unable to align NIFTY ratio and price histories')
    latest=d.iloc[-1]; latest_date=d.index[-1]
    if (end-latest_date).days>7:raise RuntimeError('NIFTY observations are over seven calendar days old')
    md=d[d.index>=date(2021,5,1)].copy(); md.index=pd.to_datetime(md.index)
    m=md.groupby(md.index.to_period('M')).tail(1)
    hist=[[idx.strftime('%Y-%m'),round(float(row.pe),4),round(float(row.pb),4),None if pd.isna(row.dy) else round(float(row.dy),4)] for idx,row in m.iterrows()]
    eps=(d['level']/d['pe']).copy(); eps.index=pd.to_datetime(eps.index)
    em=eps.groupby(eps.index.to_period('M')).last().sort_index()
    # Use completed months for cycle comparisons, not a partial month versus a month-end.
    em=em[em.index<pd.Period(end,freq='M')].asfreq('M')
    em=em.reindex(pd.period_range(em.index.min(),em.index.max(),freq='M'))
    g12=100*(em/em.shift(12)-1); accel=g12-g12.shift(6)
    zg=robust_z(g12,3.0); za=robust_z(accel,3.0)
    zparts=[x for x in [(0.7,zg),(0.3,za)] if x[1] is not None]
    escore=float(np.tanh(sum(w*z for w,z in zparts)/sum(w for w,z in zparts)/1.5)) if zparts else None
    return {
      'latest':{'date':latest_date.isoformat(),'level':float(latest.level),'pe':float(latest.pe),'pb':float(latest.pb),'div_yield':None if pd.isna(latest.dy) else float(latest.dy)},
      'history':hist,
      'earnings':{'eps':float(em.iloc[-1]),'asof':str(em.index[-1].end_time.date()),'coverage':sum(w for w,z in zparts),'eps_growth_12m':None if pd.isna(g12.iloc[-1]) else float(g12.iloc[-1]),'acceleration_6m':None if pd.isna(accel.iloc[-1]) else float(accel.iloc[-1]),'score':escore}
    }


def fetch_india_gsec10():
    try:
        html=requests.get('https://www.fbil.org.in/',headers=UA,timeout=30).text
        tables=pd.read_html(StringIO(html)); candidates=[]
        for t in tables:
            cols=[str(c).strip().lower() for c in t.columns]
            if any('tenor' in c for c in cols) and any('rate' in c for c in cols):
                t.columns=cols; tc=next(c for c in cols if 'tenor' in c); rc=next(c for c in cols if 'rate' in c)
                rows=t[t[tc].astype(str).str.upper().str.replace(' ','').eq('10YR')]
                for _,r in rows.iterrows():
                    v=fnum(r[rc])
                    if v and 3<v<15: candidates.append(v)
        if candidates: return float(candidates[0]),'FBIL daily par yield'
    except Exception as e:
        print('FBIL fallback:',e,file=sys.stderr)
    df=fred('INDIRLTLT01STM')
    return float(df.value.iloc[-1]),'FRED/OECD monthly India 10-year benchmark (lagged fallback)'


def macro_data(india_gsec10):
    # Core global liquidity/risk vectors
    real=fred('DFII10')
    us10=fred('DGS10')
    usd=fred('DTWEXBGS')
    oil=fred('DCOILBRENTEU')
    fed=fred('WALCL')
    vix=fred('VIXCLS')
    # India currency competitiveness / FX pressure
    reer=fred('RBINBIS')
    inr=fred('DEXINUS')
    # China: timely business-cycle signal + slower credit impulse proxy
    cli=fred('CHNLOLITOAASTSAM')
    china_credit=fred('QCNCAM770A')  # total non-financial-sector credit, % GDP, quarterly

    usd3,usd3s=pct_change_obs(usd,63)
    oil3,oil3s=pct_change_obs(oil,63)
    fed6,fed6s=pct_change_obs(fed,26)     # weekly ~6m
    inr3,inr3s=pct_change_obs(inr,63)     # + = INR depreciation vs USD
    reer12,reer12s=pct_change_obs(reer,12)

    # India-US nominal 10Y carry spread. Use US daily latest against India latest.
    us10_now=float(us10.value.iloc[-1]); carry=float(india_gsec10-us10_now)
    # Build a historical proxy using the lagged monthly India yield for z-normalisation.
    try:
        ind_hist=fred('INDIRLTLT01STM').set_index('date')['value'].resample('ME').last()
        us_hist=us10.set_index('date')['value'].resample('ME').last()
        carry_hist=(ind_hist-us_hist).dropna()
        z_carry=robust_z(carry_hist,0.10,max_obs=120)
        # shift current reading relative to historical mean/sd rather than last monthly reading
        if len(carry_hist)>=24:
            look=carry_hist.tail(min(len(carry_hist),120)); sd=float(look.std(ddof=0))
            z_carry=float(np.clip((carry-float(look.mean()))/sd,-3,3)) if sd>.05 else z_carry
    except Exception:
        z_carry=None

    # REER: an unusually high/strengthening real exchange rate is less supportive for export competitiveness/FPI FX asymmetry.
    z_reer_level=robust_z(reer.value,0.5,max_obs=120)
    z_reer_mom=robust_z(reer12s,0.25,max_obs=120)
    if z_reer_level is not None and z_reer_mom is not None:
        z_reer=.7*z_reer_level+.3*z_reer_mom
    else:
        z_reer=z_reer_level if z_reer_level is not None else z_reer_mom

    # China cycle: CLI level relative to 100 plus momentum, and credit impulse proxy.
    cli_s=cli.set_index('date')['value'].sort_index()
    cli_mom=cli_s.diff(3).dropna()
    z_cli_level=robust_z(cli_s-100,0.05,max_obs=180)
    z_cli_mom=robust_z(cli_mom,0.03,max_obs=180)
    z_cli=None
    if z_cli_level is not None or z_cli_mom is not None:
        vals=[(.55,z_cli_level),(.45,z_cli_mom)]; vals=[x for x in vals if x[1] is not None]
        z_cli=sum(w*z for w,z in vals)/sum(w for w,z in vals)

    cc=china_credit.set_index('date')['value'].sort_index()
    # Credit impulse proxy = acceleration in the 4-quarter change of credit/GDP.
    cc_yoy=(cc-cc.shift(4)).dropna(); cc_imp=(cc_yoy-cc_yoy.shift(1)).dropna()
    credit_impulse=float(cc_imp.iloc[-1]) if len(cc_imp) else None
    z_credit=robust_z(cc_imp,0.10,max_obs=80)

    z_real=robust_z(real.value,0.15)
    z_usd=robust_z(usd3s,0.5)
    z_oil=robust_z(oil3s,1.0)
    z_fed=robust_z(fed6s,0.5)
    z_inr=robust_z(inr3s,0.25)

    # Directional weights total 100. VIX is intentionally NOT directional: it affects confidence below.
    # EM ex-India relative valuation and forward premium are reserved weights. Missing feeds lower coverage.
    factors=[
      {'key':'us_real_10y','label':'US 10Y real yield','value':float(real.value.iloc[-1]),'z':z_real,'weight':17,'sign':-1},
      {'key':'fed_assets','label':'Fed assets, 6m','value':fed6,'z':z_fed,'weight':10,'sign':+1},
      {'key':'broad_usd','label':'Broad USD, 3m','value':usd3,'z':z_usd,'weight':13,'sign':-1},
      {'key':'brent','label':'Brent, 3m','value':oil3,'z':z_oil,'weight':12,'sign':-1},
      {'key':'carry_spread','label':'India-US 10Y yield spread','value':carry,'z':z_carry,'weight':14,'sign':+1},
      {'key':'india_reer','label':'India REER','value':float(reer.value.iloc[-1]),'z':z_reer,'weight':9,'sign':-1},
      {'key':'inr_spot','label':'USD/INR, 3m','value':inr3,'z':z_inr,'weight':5,'sign':-1},
      {'key':'china_cli','label':'China OECD leading indicator','value':float(cli.value.iloc[-1]),'z':z_cli,'weight':8,'sign':+1},
      {'key':'china_credit','label':'China credit impulse proxy','value':credit_impulse,'z':z_credit,'weight':5,'sign':+1},
      {'key':'inr_forward','label':'USD/INR forward premium','value':None,'z':None,'weight':3,'sign':-1},
      {'key':'em_ex_india_val','label':'EM ex-India relative valuation','value':None,'z':None,'weight':4,'sign':+1},
    ]
    score,coverage=directional_score(factors)

    return {
      'us_real_10y':float(real.value.iloc[-1]),
      'us_nominal_10y':us10_now,
      'india_us_10y_spread':carry,
      'usd_3m_pct':usd3,
      'brent_3m_pct':oil3,
      'fed_assets_6m_pct':fed6,
      'vix':float(vix.value.iloc[-1]),
      'india_reer':float(reer.value.iloc[-1]),
      'india_reer_12m_pct':reer12,
      'usd_inr_3m_pct':inr3,
      'china_cli':float(cli.value.iloc[-1]),
      'china_credit_impulse_proxy':credit_impulse,
      'inr_forward_premium_6m':None,
      'em_ex_india_relative_valuation':None,
      'score':score,
      'coverage':coverage,
      'factors':factors,
      'optional_pending':['USD/INR forward premium','MSCI EM ex-India relative valuation']
    }


def main():
    n=fetch_nifty()
    g10,gsrc=fetch_india_gsec10()
    mac=macro_data(g10)
    latest=n['latest']; latest['gsec10']=g10
    mandatory=[latest.get(k) for k in ['level','pe','pb','div_yield','gsec10']]
    if any(v is None or not math.isfinite(float(v)) or float(v)<=0 for v in mandatory):
        raise RuntimeError('Mandatory input failed validation; retaining old JSON')

    # Confidence is separate from macro direction. Penalise market stress AND missing macro coverage.
    vix=mac.get('vix') or 20
    stress=float(np.clip(1-max(0,vix-18)/40,0.35,1.0))
    coverage=float(mac.get('coverage',0))
    confidence=float(np.clip(stress*(0.65+0.35*coverage),0.25,1.0))

    out={
      'generated_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
      'model_version':'2.1-macro',
      'nifty':latest,
      'earnings':n['earnings'],
      'macro':mac,
      'confidence':confidence,
      'history':n['history'],
      'sources':[
        {'name':'Nifty Indices / NSE','role':'NIFTY 50 level, P/E, P/B and dividend yield'},
        {'name':gsrc,'role':'India 10-year government bond yield'},
        {'name':'FRED / Federal Reserve','role':'US nominal & real yields, broad USD, Fed assets, VIX, Brent and USD/INR spot'},
        {'name':'BIS via FRED','role':'India real effective exchange rate and China credit/GDP'},
        {'name':'OECD via FRED','role':'China composite leading indicator'},
        {'name':'RBI/FBIL (optional)','role':'USD/INR forward premium when a robust unattended endpoint is available'},
        {'name':'MSCI (optional)','role':'EM ex-India relative valuation when a stable machine-readable feed is available'}
      ]
    }
    tmp=OUT.with_suffix('.tmp')
    tmp.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8')
    tmp.replace(OUT)
    print(f'Updated {OUT} for NIFTY date {latest["date"]}; macro coverage={coverage:.0%}')

if __name__=='__main__':
    # Preserve the old command while routing it through the reviewed entry point.
    from update_data_v3 import main as reviewed_main
    reviewed_main()
