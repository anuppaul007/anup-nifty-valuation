"""Macro V3 for Anup Nifty Valuation.

Key rule: every macro feed is independent. One failed provider must never zero the
whole macro engine. Available factors are scored; missing factors are excluded and
weights are renormalized. Current values also carry source/status metadata.
"""
from __future__ import annotations
from datetime import date
from io import StringIO
from urllib.parse import urljoin
import math,re,sys,time
import numpy as np, pandas as pd, requests
from bs4 import BeautifulSoup
import update_data as b

UA={'User-Agent':'Mozilla/5.0 (compatible; AnupNiftyValuation/3.1; personal research dashboard)'}


def squash(x,s=1.5): return float(np.tanh(float(x)/s))
def zhist(x,h,n=24,floor=1e-9):
    if x is None:return None
    s=pd.Series(h,dtype='float64').dropna()
    if len(s)<n:return None
    sd=float(s.std(ddof=0))
    if not math.isfinite(sd) or sd<floor:return None
    return float(np.clip((float(x)-float(s.mean()))/sd,-3,3))
def weighted(items):
    u=[(float(s),float(w)) for s,w in items if s is not None and math.isfinite(float(s)) and w>0]
    if not u:return 0.0,0.0
    w=sum(x[1] for x in u);return sum(s*ww for s,ww in u)/w,w
def pc(df,lag):
    if df is None or len(df)<lag+2:return None,pd.Series(dtype=float)
    s=df.set_index('date')['value'].sort_index(); q=(100*(s/s.shift(lag)-1)).dropna()
    return (float(q.iloc[-1]) if len(q) else None),q
def rz(s,n=24,floor=1e-9):
    q=pd.Series(s,dtype='float64').dropna()
    z=zhist(float(q.iloc[-1]),q.iloc[:-1],max(12,n-1),floor) if len(q)>=n else None
    return 0.0 if z is None else z

def safe(label,fn):
    try:return fn()
    except Exception as e:
        print(f'{label} unavailable: {type(e).__name__}: {e}',file=sys.stderr)
        return None

def _series_from_row_table(url,desc_contains):
    """Parse Federal Reserve DownloadTable pages whose dates are columns."""
    r=requests.get(url,headers=UA,timeout=25);r.raise_for_status()
    tabs=pd.read_html(StringIO(r.text))
    for t in tabs:
        if t.empty:continue
        for _,row in t.iterrows():
            joined=' '.join(str(v) for v in row.iloc[:2].tolist())
            if desc_contains.lower() not in joined.lower():continue
            pts=[]
            for c,v in row.items():
                dt=pd.to_datetime(str(c),errors='coerce')
                val=b.fnum(v)
                if not pd.isna(dt) and val is not None:pts.append((dt,val))
            if len(pts)>=4:
                return pd.DataFrame(pts,columns=['date','value']).sort_values('date').reset_index(drop=True)
    raise RuntimeError(f'Federal Reserve table did not contain {desc_contains}')

def fed_broad_usd():
    # Official Federal Reserve H.10 monthly broad-dollar package, 120 observations.
    url=('https://www.federalreserve.gov/datadownload/DownloadTable.aspx?filetype=csv&label=include'
         '&lastobs=120&layout=seriescolumn&rel=H10&series=847be2166a425bda9b4d92465f797544&type=package')
    return _series_from_row_table(url,'Nominal Broad Dollar Index')

def fed_assets():
    # Official Federal Reserve H.4.1 total-assets package, ~2 years weekly.
    url=('https://www.federalreserve.gov/datadownload/DownloadTable.aspx?filetype=csv&label=include'
         '&lastobs=120&layout=seriescolumn&rel=H41&series=17398fbf71bc6a47df150bceebdea2bc&type=package')
    return _series_from_row_table(url,'Assets: Total Assets')

def treasury_curve(real=False):
    y=date.today().year
    typ='daily_treasury_real_yield_curve' if real else 'daily_treasury_yield_curve'
    url=(f'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/'
         f'daily-treasury-rates.csv/{y}/all?type={typ}&field_tdr_date_value={y}&page&_format=csv')
    r=requests.get(url,headers=UA,timeout=25);r.raise_for_status()
    df=pd.read_csv(StringIO(r.text))
    dc=next((c for c in df.columns if str(c).strip().lower()=='date'),None)
    vc=next((c for c in df.columns if str(c).strip().upper() in ('10 YR','10-YEAR','10 YEAR')),None)
    if dc is None or vc is None:raise RuntimeError('Treasury 10Y columns not found')
    q=pd.DataFrame({'date':pd.to_datetime(df[dc],errors='coerce'),'value':pd.to_numeric(df[vc],errors='coerce')}).dropna().sort_values('date')
    if len(q)<20:raise RuntimeError('Treasury returned too few observations')
    return q.reset_index(drop=True)

def cboe_vix():
    url='https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv'
    r=requests.get(url,headers=UA,timeout=25);r.raise_for_status();df=pd.read_csv(StringIO(r.text))
    dc=next(c for c in df.columns if str(c).strip().upper()=='DATE');vc=next(c for c in df.columns if str(c).strip().upper()=='CLOSE')
    q=pd.DataFrame({'date':pd.to_datetime(df[dc],errors='coerce'),'value':pd.to_numeric(df[vc],errors='coerce')}).dropna().sort_values('date')
    if q.empty:raise RuntimeError('CBOE VIX empty')
    return q.reset_index(drop=True)

def yahoo_series(symbol,range_='2y'):
    url=f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
    r=requests.get(url,params={'range':range_,'interval':'1d','events':'history'},headers=UA,timeout=25);r.raise_for_status();j=r.json()
    x=j['chart']['result'][0];ts=x.get('timestamp') or [];cl=(x.get('indicators',{}).get('quote',[{}])[0].get('close') or [])
    pts=[(pd.to_datetime(t,unit='s'),float(v)) for t,v in zip(ts,cl) if v is not None and math.isfinite(float(v))]
    if len(pts)<80:raise RuntimeError(f'Yahoo {symbol} too few observations')
    return pd.DataFrame(pts,columns=['date','value']).sort_values('date').reset_index(drop=True)

def fred_optional(series):
    return safe('FRED '+series,lambda:b.fred(series))

def stoxx(month=None):
    url='https://stoxx.com/index/swexiagv/'+(('?d='+month+'&factsheet=true') if month else '?factsheet=true')
    r=requests.get(url,headers=UA,timeout=18);r.raise_for_status()
    for t in pd.read_html(StringIO(r.text)):
        for _,row in t.iterrows():
            if not any('Emerging Markets ex India' in str(v) for v in row.tolist()):continue
            nums=[b.fnum(v) for v in row.tolist()];nums=[v for v in nums if v is not None]
            if len(nums)>=6 and 5<nums[0]<50 and .2<nums[4]<10:
                m=re.search(r'all data as of\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})',r.text,re.I);asof=None
                if m:
                    try:asof=pd.to_datetime(m.group(1)).date().isoformat()
                    except:pass
                return {'pe':float(nums[0]),'pb':float(nums[4]),'div_yield':float(nums[5]),'asof':asof}
    raise RuntimeError('STOXX EM ex-India fundamentals not parsed')

def relative_em(nifty,hist,old):
    prior=(((old or {}).get('calibration') or {}).get('em_ex_india_history') or [])
    by={str(x.get('month')):x for x in prior if isinstance(x,dict) and x.get('month')}
    cur=safe('STOXX current',stoxx)
    if len(by)<18:
        nh={r[0]:{'pe':r[1],'pb':r[2]} for r in hist}
        missing=[mon for mon in sorted(nh)[-24:] if mon not in by][-4:]
        for mon in missing:
            em=safe('STOXX archive '+mon,lambda m=mon:stoxx(m))
            if em:
                rel=.6*math.log(nh[mon]['pe']/em['pe'])+.4*math.log(nh[mon]['pb']/em['pb'])
                by[mon]={'month':mon,'em_pe':em['pe'],'em_pb':em['pb'],'nifty_pe':nh[mon]['pe'],'nifty_pb':nh[mon]['pb'],'relative_log_premium':rel};time.sleep(.05)
    hh=sorted(by.values(),key=lambda x:x['month'])[-60:];out={'available':bool(cur),'history_count':len(hh),'score':None}
    if cur:
        rel=.6*math.log(nifty['pe']/cur['pe'])+.4*math.log(nifty['pb']/cur['pb']);z=zhist(rel,[x.get('relative_log_premium') for x in hh],12,.03)
        out.update({'em_ex_india_pe':cur['pe'],'em_ex_india_pb':cur['pb'],'em_ex_india_div_yield':cur['div_yield'],'asof':cur.get('asof'),'nifty_pe_premium_pct':100*(nifty['pe']/cur['pe']-1),'nifty_pb_premium_pct':100*(nifty['pb']/cur['pb']-1),'relative_log_premium':rel,'z':z,'score':None if z is None else squash(-z)})
    return out,hh

def china_pmi():
    base='https://www.stats.gov.cn/english/PressRelease/';cand=[]
    for i in range(7):
        url=base+('index.html' if i==0 else f'index_{i}.html')
        try:
            r=requests.get(url,headers=UA,timeout=15)
            if r.status_code!=200:continue
            for a in BeautifulSoup(r.text,'lxml').find_all('a',href=True):
                txt=' '.join(a.stripped_strings)
                if 'Purchasing Managers' in txt and 'Index for' in txt:
                    m=re.search(r'for\s+([A-Za-z]+)\s+(\d{4})',txt)
                    if m:
                        dt=pd.to_datetime(f'{m.group(1)} 1 {m.group(2)}',errors='coerce')
                        if not pd.isna(dt):cand.append((dt,urljoin(url,a['href'])))
        except:pass
    if not cand:raise RuntimeError('NBS PMI release not found')
    _,url=max(cand,key=lambda x:x[0]);r=requests.get(url,headers=UA,timeout=20);r.raise_for_status();txt=BeautifulSoup(r.text,'lxml').get_text(' ',strip=True)
    pmi=None
    for pat in [r'manufacturing industry(?:\s+came in at|\s+was|\s+stood at)\s+([0-9]+(?:\.[0-9]+)?)%',r'manufacturing sector(?:\s+stood at|\s+was)\s+([0-9]+(?:\.[0-9]+)?)']:
        m=re.search(pat,txt,re.I)
        if m:pmi=float(m.group(1));break
    if pmi is None or not 35<pmi<65:raise RuntimeError('NBS PMI value not parsed')
    m=re.search(r'new order index was\s+([0-9]+(?:\.[0-9]+)?)%',txt,re.I);orders=float(m.group(1)) if m else None
    dm=re.search(r'Purchasing Managers.? Index for\s+([A-Za-z]+\s+\d{4})',txt,re.I);period=pd.to_datetime(dm.group(1)).strftime('%Y-%m') if dm else None
    score=squash(.7*((pmi-50)/1.75)+.3*(0 if orders is None else (orders-50)/2.0))
    return {'pmi':pmi,'new_orders':orders,'period':period,'score':score,'source_url':url}

def ccil_forward():
    url='https://dr.ccilindia.com/web/ccil/interbank-usd-inr-spot-fwd1';r=requests.get(url,headers=UA,timeout=20);r.raise_for_status()
    for t in pd.read_html(StringIO(r.text)):
        for _,row in t.iterrows():
            first=str(row.iloc[0]).lower()
            if '1 month' not in first and first.strip()!='1m':continue
            for v in row.iloc[1:]:
                for x in reversed(re.findall(r'\(([-+]?\d+(?:\.\d+)?)\)',str(v))):
                    x=float(x)
                    if 0<=x<=15:return {'one_month_pct':x,'source_url':url}
    return None

def carry(india,us,old):
    usnow=float(us.value.iloc[-1]);cur=float(india)-usnow;z=None
    # Prefer historical India monthly series when FRED is reachable, but do not fail the macro engine.
    ind=fred_optional('INDIRLTLT01STM')
    if ind is not None:
        usm=us.set_index('date')['value'].resample('MS').mean();im=ind.set_index('date')['value'].resample('MS').mean();x=pd.concat([im.rename('i'),usm.rename('u')],axis=1).dropna();h=(x.i-x.u).dropna();z=zhist(cur,h.tolist(),24,.15)
    if z is None:
        hist=(((old or {}).get('calibration') or {}).get('carry_spread_history') or [])
        vals=[x.get('value') for x in hist if isinstance(x,dict) and x.get('value') is not None]
        z=zhist(cur,vals,12,.15) if vals else None
    return {'india_us_10y_spread':cur,'us_10y':usnow,'z':z,'score':None if z is None else squash(z)}

def build(india_g10,nifty,nifty_hist,old):
    prior=(old or {}).get('macro') or {}
    sources={};stale=[]
    real=safe('US Treasury real 10Y',lambda:treasury_curve(True)); sources['us_real_10y']='U.S. Treasury' if real is not None else None
    us10=safe('US Treasury nominal 10Y',lambda:treasury_curve(False)); sources['us_10y']='U.S. Treasury' if us10 is not None else None
    usd=safe('Federal Reserve broad USD',fed_broad_usd); sources['broad_usd']='Federal Reserve H.10' if usd is not None else None
    fed=safe('Federal Reserve assets',fed_assets); sources['fed_assets']='Federal Reserve H.4.1' if fed is not None else None
    vix=safe('CBOE VIX',cboe_vix); sources['vix']='CBOE' if vix is not None else None
    oil=safe('Brent',lambda:yahoo_series('BZ=F')); sources['brent']='Yahoo Finance Brent futures' if oil is not None else None
    reer=fred_optional('RBINBIS'); sources['india_reer']='BIS via FRED' if reer is not None else None

    usd3,usd3s=pc(usd,3) if usd is not None else (None,pd.Series(dtype=float)) # monthly H.10
    oil3,oil3s=pc(oil,63) if oil is not None else (None,pd.Series(dtype=float))
    fed6,fed6s=pc(fed,26) if fed is not None else (None,pd.Series(dtype=float)) # weekly H.4.1
    zr=rz(real.value,60,.15) if real is not None else None;zu=rz(usd3s,36,.4) if len(usd3s) else None;zo=rz(oil3s,60,1) if len(oil3s) else None;zf=rz(fed6s,40,.4) if len(fed6s) else None;zreer=rz(reer.value,48,1) if reer is not None else None
    gl,glcov=weighted([(None if zr is None else squash(-zr),.50),(None if zf is None else squash(zf),.25),(None if zu is None else squash(-zu),.25)])

    ca=carry(india_g10,us10,old) if us10 is not None else {'india_us_10y_spread':None,'us_10y':None,'z':None,'score':None}
    fwd=safe('CCIL forward premium',ccil_forward);fh=[x for x in (((old or {}).get('calibration') or {}).get('forward_premium_history') or []) if isinstance(x,dict) and x.get('value') is not None]
    if fwd:
        today=date.today().isoformat();fh=[x for x in fh if x.get('date')!=today];fh.append({'date':today,'value':fwd['one_month_pct']})
    fh=fh[-180:];zfwd=None;sfwd=None
    if fwd and len(fh)>=20:
        zfwd=zhist(fwd['one_month_pct'],[x['value'] for x in fh[:-1]],18,.15);sfwd=None if zfwd is None else squash(-zfwd)
    ext,extcov=weighted([(None if zo is None else squash(-zo),.35),(ca.get('score'),.30),(None if zreer is None else squash(-zreer),.20),(sfwd,.15)])

    ch=safe('China PMI',china_pmi)
    rel,rh=relative_em(nifty,nifty_hist,old)
    block_items=[(gl if glcov>0 else None,.30),(ext if extcov>0 else None,.30),(None if not ch else ch.get('score'),.20),(rel.get('score'),.20)]
    score,cov=weighted(block_items)

    # If a current display value is temporarily missing, show previous value but do not score it unless its score was also independently available this run.
    def cur(df,key):
        if df is not None and len(df):return float(df.value.iloc[-1])
        return prior.get(key)
    real_now=cur(real,'us_real_10y');vix_now=cur(vix,'vix');reer_now=cur(reer,'india_reer_bis')
    if real is None:stale.append('US real 10Y')
    if usd is None:stale.append('Broad USD')
    if oil is None:stale.append('Brent')
    if fed is None:stale.append('Fed assets')
    if vix is None:stale.append('VIX')
    if us10 is None:stale.append('US nominal 10Y')
    if reer is None:stale.append('India REER')

    # Maintain a small carry-history cache independent of FRED availability.
    carryhist=[x for x in (((old or {}).get('calibration') or {}).get('carry_spread_history') or []) if isinstance(x,dict) and x.get('value') is not None]
    if ca.get('india_us_10y_spread') is not None:
        mon=date.today().strftime('%Y-%m');carryhist=[x for x in carryhist if x.get('month')!=mon];carryhist.append({'month':mon,'value':ca['india_us_10y_spread']})
    carryhist=carryhist[-120:]

    macro={
      'us_real_10y':real_now,'fed_assets_6m_pct':fed6 if fed6 is not None else prior.get('fed_assets_6m_pct'),'usd_3m_pct':usd3 if usd3 is not None else prior.get('usd_3m_pct'),'brent_3m_pct':oil3 if oil3 is not None else prior.get('brent_3m_pct'),'vix':vix_now,
      'india_reer_bis':reer_now,'india_reer_z':zreer,'us_10y':ca.get('us_10y') if ca.get('us_10y') is not None else prior.get('us_10y'),'india_us_10y_spread':ca.get('india_us_10y_spread') if ca.get('india_us_10y_spread') is not None else prior.get('india_us_10y_spread'),'india_us_spread_z':ca.get('z'),
      'forward_premium_1m':None if not fwd else fwd['one_month_pct'],'forward_premium_z':zfwd,'china_pmi':ch,'relative_em':rel,
      'blocks':{'global_liquidity':gl if glcov>0 else None,'india_external_carry':ext if extcov>0 else None,'china_industrial':None if not ch else ch.get('score'),'relative_em_valuation':rel.get('score')},
      'score':score,'active_block_weight':cov,'sources_live':sources,'stale_factors':stale,
      'factor_coverage':{'global_liquidity':glcov,'india_external_carry':extcov,'block_weight':cov}
    }
    cal={'em_ex_india_history':rh,'forward_premium_history':fh,'carry_spread_history':carryhist}
    return macro,cal
