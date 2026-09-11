"""Independent, dated macro factors for Anup Nifty Valuation V3.4."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from io import StringIO
from urllib.parse import urljoin
import csv, math, re, sys
import numpy as np
import pandas as pd
from lxml import html
import http_client as requests
import update_data as b

UA={'User-Agent':'Mozilla/5.0 (compatible; AnupNiftyValuation/3.4; personal research)'}
STOXX_URL='https://stoxx.com/index/swexiagv/?factsheet=true'
BLOCKS={'global_liquidity':.30,'india_external_carry':.30,'china_industrial':.20,'relative_em_valuation':.20}

def squash(x,s=1.5):return float(np.tanh(float(x)/s))
def finite(x):
    try:return x is not None and math.isfinite(float(x))
    except (TypeError,ValueError):return False
def safe(label,fn):
    try:return fn()
    except Exception as e:
        print(f'{label} unavailable: {type(e).__name__}: {e}',file=sys.stderr)
        return None
def zhist(x,h,n=24,floor=1e-9):
    if not finite(x):return None
    s=pd.to_numeric(pd.Series(h,dtype='float64'),errors='coerce').replace([np.inf,-np.inf],np.nan).dropna()
    if len(s)<n:return None
    sd=float(s.std(ddof=0))
    if sd<floor:return None
    return float(np.clip((float(x)-float(s.mean()))/sd,-3,3))
def rz(s,n=24,floor=1e-9,max_obs=756):
    q=pd.Series(s,dtype='float64').replace([np.inf,-np.inf],np.nan).dropna()
    return zhist(q.iloc[-1],q.iloc[:-1].tail(max_obs),n,floor) if len(q)>n else None
def weighted(items):
    active=[(float(v),float(w)) for v,w in items if finite(v) and finite(w) and w>0]
    total=sum(w for _,w in active)
    return (sum(v*w for v,w in active)/total,total) if total else (None,0.0)
def pc(df,lag):
    if df is None or len(df)<=lag:return None,pd.Series(dtype=float)
    s=df.set_index('date')['value'].sort_index()
    q=(100*(s/s.shift(lag)-1)).replace([np.inf,-np.inf],np.nan).dropna()
    current=100*(s.iloc[-1]/s.iloc[-1-lag]-1)
    return (float(current) if finite(current) else None),q
def clean(df,source,asof=None):
    q=df.copy()
    q['date']=pd.to_datetime(q['date'],errors='coerce')
    q['value']=pd.to_numeric(q['value'],errors='coerce')
    q=q.replace([np.inf,-np.inf],np.nan).dropna().sort_values('date').drop_duplicates('date')
    q=q[q.date.dt.date<=date.today()].reset_index(drop=True)
    if q.empty:raise RuntimeError('No dated observations')
    q.attrs={'source':source,'asof':asof or q.date.iloc[-1].date().isoformat()}
    return q
def fresh(asof,max_age):
    try:
        age=(date.today()-date.fromisoformat(str(asof)[:10])).days
        return 0<=age<=max_age
    except (ValueError,TypeError):return False
def fred_optional(series):return safe('FRED '+series,lambda:b.fred(series))
def _fed_csv(text,description,url):
    rows=list(csv.reader(StringIO(text.lstrip('\ufeff'))))
    norm=lambda s:re.sub(r'[^a-z0-9]','',s.lower())
    desc=next((r for r in rows if r and norm(r[0])=='seriesdescription'),None)
    for i,row in enumerate(rows):
        if not row or norm(row[0]) not in ('timeperiod','date','observationdate'):continue
        if desc:
            candidates=[j for j,v in enumerate(desc[1:],1) if norm(description) in norm(v)]
            if len(candidates)>1:
                candidates=[j for j in candidates if 'wednesday' in desc[j].lower()]
            if len(candidates)!=1:raise RuntimeError('Federal Reserve CSV series is missing or ambiguous')
            column=candidates[0]
        elif len(row)==2:column=1
        else:raise RuntimeError('Federal Reserve multi-series CSV has no descriptions')
        pts=[(r[0],r[column]) for r in rows[i+1:] if len(r)>column]
        return clean(pd.DataFrame(pts,columns=['date','value']),url)
    raise RuntimeError('Federal Reserve CSV date header not found')
def _fed_table(url,description):
    r=requests.get(url,headers=UA);r.raise_for_status()
    if not r.text.lstrip().startswith('<'):
        return _fed_csv(r.text,description,url)
    for t in pd.read_html(StringIO(r.text)):
        for _,row in t.iterrows():
            if description.lower() not in ' '.join(map(str,row.iloc[:2])).lower():continue
            pts=[]
            for c,v in row.items():
                stamp=pd.to_datetime(str(c),errors='coerce')
                if not pd.isna(stamp) and finite(b.fnum(v)):pts.append((stamp,b.fnum(v)))
            if pts:return clean(pd.DataFrame(pts,columns=['date','value']),url)
    raise RuntimeError('Federal Reserve series not found')
def fed_broad_usd():
    q=fred_optional('DTWEXBGS')
    if q is not None:
        q=clean(q,'https://fred.stlouisfed.org/series/DTWEXBGS')
        m=q.set_index('date').value.resample('MS').mean().reset_index()
        m=m[m.date<pd.Timestamp(date.today().replace(day=1))]
        asof=str(m.date.iloc[-1].to_period('M').end_time.date())
        return clean(m,q.attrs['source'],asof)
    # Output.aspx downloads the requested history; DownloadTable.aspx is only a preview.
    q=_fed_table('https://www.federalreserve.gov/datadownload/Output.aspx?filetype=csv&label=include&lastobs=120&layout=seriescolumn&rel=H10&series=847be2166a425bda9b4d92465f797544&type=package','Nominal Broad Dollar Index')
    source=q.attrs['source'];q=q[q.date<pd.Timestamp(date.today().replace(day=1))]
    return clean(q,source,str(q.date.iloc[-1].to_period('M').end_time.date()))
def fed_assets():
    q=fred_optional('WALCL')
    if q is not None:return clean(q,'https://fred.stlouisfed.org/series/WALCL')
    return _fed_table('https://www.federalreserve.gov/datadownload/Output.aspx?filetype=csv&label=include&lastobs=180&layout=seriescolumn&rel=H41&series=17398fbf71bc6a47df150bceebdea2bc&type=package','Assets: Total Assets')
def treasury_curve(real=False):
    typ='daily_treasury_real_yield_curve' if real else 'daily_treasury_yield_curve'
    parts=[]
    # A year boundary must not reset calibration to a few days.
    for y in range(date.today().year-3,date.today().year+1):
        url=f'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{y}/all?type={typ}&field_tdr_date_value={y}&page&_format=csv'
        def one():
            r=requests.get(url,headers=UA);r.raise_for_status()
            t=pd.read_csv(StringIO(r.text))
            dc=next(c for c in t.columns if str(c).strip().lower()=='date')
            vc=next(c for c in t.columns if str(c).strip().upper() in ('10 YR','10-YEAR','10 YEAR'))
            return pd.DataFrame({'date':t[dc],'value':t[vc]})
        q=safe(f'Treasury {y}',one)
        if q is not None:parts.append(q)
    if not parts:raise RuntimeError('Treasury history unavailable')
    return clean(pd.concat(parts),url)
def cboe_vix():
    url='https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv'
    t=pd.read_csv(StringIO(requests.get(url,headers=UA).text))
    return clean(pd.DataFrame({'date':t['DATE'],'value':t['CLOSE']}),url)
def yahoo_series(symbol):
    url=f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
    j=requests.get(url,params={'range':'3y','interval':'1d','events':'history'},headers=UA).json()['chart']['result'][0]
    pts=[(pd.to_datetime(t,unit='s'),v) for t,v in zip(j['timestamp'],j['indicators']['quote'][0]['close']) if finite(v)]
    return clean(pd.DataFrame(pts,columns=['date','value']),url)

def parse_stoxx(text):
    """Bind by the named fundamentals headers; never scan a risk/performance row."""
    page=' '.join(html.fromstring(text).text_content().split())
    dm=re.search(r'all data as of\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})',page,re.I)
    asof=pd.to_datetime(dm.group(1)).date().isoformat() if dm else None
    for t in pd.read_html(StringIO(text)):
        labels=[' '.join(map(str,c)) if isinstance(c,tuple) else str(c) for c in t.columns]
        def col(label,trailing=False):
            matches=[i for i,c in enumerate(labels) if label.lower() in c.lower() and (not trailing or 'trailing' in c.lower())]
            if len(matches)!=1:raise ValueError('Ambiguous fundamentals column: '+label)
            return matches[0]
        if not any('Price/earnings incl. negative' in c for c in labels):continue
        ip,ib,iy=col('Price/earnings incl. negative',True),col('Price/book',True),col('Dividend yield')
        for _,row in t.iterrows():
            if str(row.iloc[0]).strip()!='STOXX Emerging Markets ex India Universal All Cap':continue
            pe,pb,dy=[b.fnum(row.iloc[i]) for i in (ip,ib,iy)]
            if not all(finite(v) for v in (pe,pb,dy)) or not (0<pe<200 and 0<pb<30 and 0<=dy<30):raise ValueError('Invalid EM fundamentals')
            return {'pe':pe,'pb':pb,'div_yield':dy,'asof':asof,'source_url':STOXX_URL,'method':'fundamentals-v1','pe_basis':'Trailing, including negative earnings'}
    raise RuntimeError('STOXX named fundamentals table not found')
def stoxx():return parse_stoxx(requests.get(STOXX_URL,headers=UA).text)
def relative_em(nifty,hist,old):
    # V3.3 history contains volatility/Sharpe data. Only accept corrected, dated pairs.
    prior=((old or {}).get('calibration') or {}).get('em_ex_india_history') or []
    by={x['month']:x for x in prior if x.get('method')=='fundamentals-v1' and x.get('asof','')[:7]==x.get('month')}
    cur=safe('STOXX',stoxx)
    out={'available':bool(cur),'score':None,'history_count':0,'status':'unavailable'}
    if cur:
        mon=(cur.get('asof') or '')[:7]
        pair=next((x for x in hist if x[0]==mon),None)
        out.update({'em_ex_india_pe':cur['pe'],'em_ex_india_pb':cur['pb'],'em_ex_india_div_yield':cur['div_yield'],'asof':cur['asof'],'source_url':STOXX_URL,'pe_basis':cur['pe_basis'],'method':cur['method'],'status':'pending_history'})
        if pair and mon<date.today().strftime('%Y-%m'):
            rel=.6*math.log(pair[1]/cur['pe'])+.4*math.log(pair[2]/cur['pb'])
            refs=[v['relative_log_premium'] for k,v in by.items() if k<mon]
            z=zhist(rel,refs,12,.03)
            out.update({'comparison_month':mon,'relative_log_premium':rel,'nifty_pe_premium_pct':100*(pair[1]/cur['pe']-1),'nifty_pb_premium_pct':100*(pair[2]/cur['pb']-1),'history_count':len(refs),'z':z})
            if z is not None and fresh(cur['asof'],100):out.update(score=squash(-z),status='live')
            by[mon]={'month':mon,'asof':cur['asof'],'method':cur['method'],'em_pe':cur['pe'],'em_pb':cur['pb'],'nifty_pe':pair[1],'nifty_pb':pair[2],'relative_log_premium':rel}
        if not fresh(cur['asof'],100):out.update(score=None,status='stale')
    return out,sorted(by.values(),key=lambda x:x['month'])[-60:]
def parse_china(text,period=None,source_url=None):
    page=' '.join(html.fromstring(text).text_content().split())
    dm=re.search(r'Purchasing Managers.{0,3} Index for\s+([A-Za-z]+\s+\d{4})',page,re.I)
    if dm:period=pd.to_datetime(dm.group(1)).strftime('%Y-%m')
    pm=None
    for pat in [r'manufacturing industry(?:\s+came in at|\s+was|\s+stood at)\s+(\d+(?:\.\d+)?)',r'manufacturing sector(?:\s+stood at|\s+was)\s+(\d+(?:\.\d+)?)']:
        match=re.search(pat,page,re.I)
        if match:pm=float(match.group(1));break
    om=re.search(r'new orders? index (?:was|stood at)\s+(\d+(?:\.\d+)?)',page,re.I)
    orders=float(om.group(1)) if om else None
    if pm is None or not 35<pm<65:raise RuntimeError('Manufacturing PMI not parsed')
    if orders is not None and not 25<orders<75:orders=None
    raw,cov=weighted([((pm-50)/1.75,.7),(None if orders is None else (orders-50)/2,.3)])
    asof=str(pd.Period(period,freq='M').end_time.date()) if period else None
    ok=fresh(asof,70)
    return {'pmi':pm,'new_orders':orders,'period':period,'asof':asof,'score':squash(raw) if ok else None,'coverage':cov if ok else 0,'status':'live' if ok else 'stale','source_url':source_url}
def china_pmi():
    base='https://www.stats.gov.cn/english/PressRelease/';cand=[]
    for i in range(3):
        url=base+('index.html' if i==0 else f'index_{i}.html')
        def links():
            tree=html.fromstring(requests.get(url,headers=UA).text)
            return [(a.text_content(),urljoin(url,a.get('href'))) for a in tree.xpath('//a[@href]')]
        for txt,link in safe('NBS index',links) or []:
            m=re.search(r'Purchasing Managers.{0,3} Index for\s+([A-Za-z]+)\s+(\d{4})', ' '.join(txt.split()),re.I)
            if m:
                dt=pd.to_datetime(f'{m[1]} 1 {m[2]}',errors='coerce')
                if not pd.isna(dt) and dt.date()<=date.today():cand.append((dt,link))
        if cand:break
    if not cand:raise RuntimeError('NBS dated PMI release not found')
    dt,url=max(cand,key=lambda x:x[0])
    return parse_china(requests.get(url,headers=UA).text,dt.strftime('%Y-%m'),url)
def ccil_forward():
    # Keep undated quotes out of calibration. A robust dated CCIL adapter is pending.
    return None

def factor(value,z,df,max_age,sign=1):
    asof=df.attrs.get('asof') if df is not None else None
    status='unavailable' if df is None else ('stale' if not fresh(asof,max_age) else ('pending_history' if z is None or not finite(value) else 'live'))
    return {'value':value,'z':z,'score':squash(sign*z) if status=='live' else None,'asof':asof,'observations':len(df) if df is not None else 0,'source_url':df.attrs.get('source') if df is not None else None,'status':status}
def coverage_adjust_macro(mac):
    details={};items=[]
    for key,w in BLOCKS.items():
        internal=float((mac.get('factor_coverage') or {}).get(key) or 0)
        val=(mac.get('blocks') or {}).get(key)
        eff=w*max(0,min(1,internal)) if finite(val) else 0
        details[key]={'strategic_weight':w,'internal_coverage':internal,'effective_weight':eff}
        items.append((val,eff))
    mac['score'],mac['active_block_weight']=weighted(items)
    mac['block_weight_detail']=details
    mac.setdefault('factor_coverage',{})['block_weight']=mac['active_block_weight']
    return mac
def build(india_g10,nifty,nifty_hist,old,gsec_meta=None):
    loaders={'real':lambda:treasury_curve(True),'us10':treasury_curve,'usd':fed_broad_usd,'fed':fed_assets,'vix':cboe_vix,'oil':lambda:yahoo_series('BZ=F'),'reer':lambda:fred_optional('RBINBIS'),'india':lambda:fred_optional('INDIRLTLT01STM')}
    def get_item(item):key,fn=item;return key,safe(key,fn)
    with ThreadPoolExecutor(max_workers=8) as pool:ds=dict(pool.map(get_item,loaders.items()))
    if ds['reer'] is not None:ds['reer']=clean(ds['reer'],'https://fred.stlouisfed.org/series/RBINBIS')
    factors={}
    for key,dfkey,lag,n,floor,age,sign in [('us_real_10y','real',None,60,.15,7,-1),('usd_3m_pct','usd',3,36,.4,75,-1),('fed_assets_6m_pct','fed',26,40,.4,15,1),('brent_3m_pct','oil',63,60,1,7,-1),('india_reer_bis','reer',None,48,1,100,-1)]:
        df=ds[dfkey]
        def compute():
            value,s=(float(df.value.iloc[-1]),df.value) if lag is None else pc(df,lag)
            max_obs=120 if dfkey in ('usd','reer') else (156 if dfkey=='fed' else 756)
            return factor(value,rz(s,n,floor,max_obs),df,age,sign)
        factors[key]=safe(key+' scoring',compute) if df is not None else None
        if factors[key] is None:factors[key]=factor(None,None,None,age)
    us=ds['us10'];iv=ds['india'];spread=None;z=None
    gvalid=finite(india_g10) and (gsec_meta or {}).get('status')!='excluded' and fresh((gsec_meta or {}).get('asof'),(gsec_meta or {}).get('max_age_days',7))
    def carry():
        if us is None or not gvalid or not fresh(us.attrs['asof'],7):return None,None
        current=float(india_g10)-float(us.value.iloc[-1]);standardized=None
        if iv is not None:
            im=iv.set_index('date').value.resample('MS').mean()
            um=us.set_index('date').value.resample('MS').mean()
            h=(im-um).dropna()
            h=h[h.index<pd.Timestamp(date.today().replace(day=1))]
            standardized=zhist(current,h.tail(60).tolist(),24,.15)
        return current,standardized
    spread,z=safe('India-US carry scoring',carry) or (None,None)
    factors['india_us_10y_spread']=factor(spread,z,us if gvalid else None,7)
    if gvalid:
        factors['india_us_10y_spread']['india_asof']=gsec_meta['asof']
        factors['india_us_10y_spread']['india_source_url']=gsec_meta.get('source_url')
    factors['forward_premium_1m']=factor(None,None,None,7)
    ch=safe('China PMI',china_pmi)
    em=safe('Relative EM',lambda:relative_em(nifty,nifty_hist,old))
    rel,rh=em if em is not None else ({'score':None,'status':'unavailable'},[])
    specs={'global_liquidity':[('us_real_10y',.5),('fed_assets_6m_pct',.25),('usd_3m_pct',.25)],'india_external_carry':[('brent_3m_pct',.35),('india_us_10y_spread',.30),('india_reer_bis',.20),('forward_premium_1m',.15)]}
    blocks={};fc={}
    for key,items in specs.items():blocks[key],fc[key]=weighted([(factors[f]['score'],w) for f,w in items])
    blocks['china_industrial']=ch.get('score') if ch else None
    fc['china_industrial']=ch.get('coverage',0) if ch else 0
    blocks['relative_em_valuation']=rel.get('score');fc['relative_em_valuation']=1 if rel.get('score') is not None else 0
    vx=ds['vix'];vmeta=factor(float(vx.value.iloc[-1]) if vx is not None else None,0,vx,7)
    factors['vix']=vmeta
    if us is not None:factors['us_10y']=factor(float(us.value.iloc[-1]),0,us,7)
    else:factors['us_10y']=factor(None,None,None,7)
    prior=(old or {}).get('macro') or {}
    # Cached display values are explicitly excluded and keep their original observation dates.
    for key,meta in factors.items():
        if meta['value'] is None and finite(prior.get(key)):
            pm=(prior.get('factors') or {}).get(key) or {}
            meta.update(value=prior[key],asof=pm.get('asof'),status='cached',score=None)
    mac={key:meta['value'] for key,meta in factors.items()}
    mac.update({'factors':factors,'china_pmi':ch,'relative_em':rel,'blocks':blocks,'factor_coverage':fc,'india_reer_z':factors['india_reer_bis']['z'],'india_us_spread_z':z,'forward_premium_z':None,'stale_factors':[k for k,v in factors.items() if v['status']!='live'],'sources_live':{k:v['source_url'] if v['status']=='live' else None for k,v in factors.items()}})
    return coverage_adjust_macro(mac),{'em_ex_india_history':rh,'forward_premium_history':[],'carry_spread_history':[]}
