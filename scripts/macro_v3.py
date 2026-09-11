"""Macro V3 for Anup Nifty Valuation. Optional feeds fail soft; weights renormalize."""
from __future__ import annotations
from datetime import date
from io import StringIO
from urllib.parse import urljoin
import math,re,sys,time
import numpy as np, pandas as pd, requests
from bs4 import BeautifulSoup
import update_data as b
UA={'User-Agent':'Mozilla/5.0 (compatible; AnupNiftyValuation/3.0; personal research dashboard)'}

def squash(x,s=1.5): return float(np.tanh(float(x)/s))
def zhist(x,h,n=24,floor=1e-9):
    if x is None:return None
    s=pd.Series(h,dtype='float64').dropna()
    if len(s)<n:return None
    sd=float(s.std(ddof=0));
    if not math.isfinite(sd) or sd<floor:return None
    return float(np.clip((float(x)-float(s.mean()))/sd,-3,3))
def weighted(items):
    u=[(float(s),float(w)) for s,w in items if s is not None and math.isfinite(float(s)) and w>0]
    if not u:return 0.0,0.0
    w=sum(x[1] for x in u);return sum(s*ww for s,ww in u)/w,w
def pc(df,lag):
    s=df.set_index('date')['value'].sort_index(); q=(100*(s/s.shift(lag)-1)).dropna()
    return (float(q.iloc[-1]) if len(q) else None),q
def rz(s,n=24,floor=1e-9):
    q=pd.Series(s,dtype='float64').dropna()
    z=zhist(float(q.iloc[-1]),q.iloc[:-1],max(12,n-1),floor) if len(q)>=n else None
    return 0.0 if z is None else z

def stoxx(month=None):
    url='https://stoxx.com/index/swexiagv/'+(('?d='+month+'&factsheet=true') if month else '?factsheet=true')
    r=requests.get(url,headers=UA,timeout=18);r.raise_for_status()
    for t in pd.read_html(StringIO(r.text)):
        for _,row in t.iterrows():
            if not any('Emerging Markets ex India' in str(v) for v in row.tolist()):continue
            nums=[b.fnum(v) for v in row.tolist()];nums=[v for v in nums if v is not None]
            if len(nums)>=6 and 5<nums[0]<50 and .2<nums[4]<10:
                m=re.search(r'all data as of\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})',r.text,re.I)
                asof=None
                if m:
                    try:asof=pd.to_datetime(m.group(1)).date().isoformat()
                    except:pass
                return {'pe':float(nums[0]),'pb':float(nums[4]),'div_yield':float(nums[5]),'asof':asof}
    raise RuntimeError('STOXX EM ex-India fundamentals not parsed')

def relative_em(nifty,hist,old):
    prior=(((old or {}).get('calibration') or {}).get('em_ex_india_history') or [])
    by={str(x.get('month')):x for x in prior if isinstance(x,dict) and x.get('month')}
    cur=None
    try:cur=stoxx()
    except Exception as e:print('STOXX current unavailable:',e,file=sys.stderr)
    if len(by)<18:
        nh={r[0]:{'pe':r[1],'pb':r[2]} for r in hist}
        missing=[mon for mon in sorted(nh)[-24:] if mon not in by][-6:]
        for mon in missing:
            try:
                em=stoxx(mon);rel=.6*math.log(nh[mon]['pe']/em['pe'])+.4*math.log(nh[mon]['pb']/em['pb'])
                by[mon]={'month':mon,'em_pe':em['pe'],'em_pb':em['pb'],'nifty_pe':nh[mon]['pe'],'nifty_pb':nh[mon]['pb'],'relative_log_premium':rel};time.sleep(.06)
            except Exception as e:print('STOXX archive skip',mon,e,file=sys.stderr)
    hh=sorted(by.values(),key=lambda x:x['month'])[-60:];out={'available':bool(cur),'history_count':len(hh),'score':None}
    if cur:
        rel=.6*math.log(nifty['pe']/cur['pe'])+.4*math.log(nifty['pb']/cur['pb'])
        z=zhist(rel,[x.get('relative_log_premium') for x in hh],12,.03)
        out.update({'em_ex_india_pe':cur['pe'],'em_ex_india_pb':cur['pb'],'em_ex_india_div_yield':cur['div_yield'],'asof':cur.get('asof'),'nifty_pe_premium_pct':100*(nifty['pe']/cur['pe']-1),'nifty_pb_premium_pct':100*(nifty['pb']/cur['pb']-1),'relative_log_premium':rel,'z':z,'score':None if z is None else squash(-z)})
    return out,hh

def china_pmi():
    base='https://www.stats.gov.cn/english/PressRelease/';cand=[]
    for i in range(9):
        url=base+('index.html' if i==0 else f'index_{i}.html')
        try:
            r=requests.get(url,headers=UA,timeout=20)
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
    _,url=max(cand,key=lambda x:x[0]);r=requests.get(url,headers=UA,timeout=30);r.raise_for_status();txt=BeautifulSoup(r.text,'lxml').get_text(' ',strip=True)
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
    url='https://dr.ccilindia.com/web/ccil/interbank-usd-inr-spot-fwd1';r=requests.get(url,headers=UA,timeout=30);r.raise_for_status()
    for t in pd.read_html(StringIO(r.text)):
        tt=t.copy();tt.columns=[' '.join(str(v) for v in c if str(v)!='nan').strip() if isinstance(c,tuple) else str(c) for c in t.columns]
        for _,row in tt.iterrows():
            first=str(row.iloc[0]).lower()
            if '1 month' not in first and first.strip()!='1m':continue
            for v in row.iloc[1:]:
                for x in reversed(re.findall(r'\(([-+]?\d+(?:\.\d+)?)\)',str(v))):
                    x=float(x)
                    if 0<=x<=15:return {'one_month_pct':x,'source_url':url}
    return None

def carry(india,us):
    usnow=float(us.value.iloc[-1]);cur=india-usnow;ind=b.fred('INDIRLTLT01STM');usm=us.set_index('date')['value'].resample('MS').mean();im=ind.set_index('date')['value'].resample('MS').mean();x=pd.concat([im.rename('i'),usm.rename('u')],axis=1).dropna();h=(x.i-x.u).dropna();z=zhist(cur,h.tolist(),36,.15)
    return {'india_us_10y_spread':cur,'us_10y':usnow,'z':z,'score':None if z is None else squash(z)}

def build(india_g10,nifty,nifty_hist,old):
    real=b.fred('DFII10');usd=b.fred('DTWEXBGS');oil=b.fred('DCOILBRENTEU');fed=b.fred('WALCL');vix=b.fred('VIXCLS');us10=b.fred('DGS10');reer=b.fred('RBINBIS')
    usd3,usd3s=pc(usd,63);oil3,oil3s=pc(oil,63);fed6,fed6s=pc(fed,26)
    zr=rz(real.value,60,.15);zu=rz(usd3s,60,.5);zo=rz(oil3s,60,1);zf=rz(fed6s,40,.5);zreer=rz(reer.value,60,1)
    gl,_=weighted([(squash(-zr),.50),(squash(zf),.25),(squash(-zu),.25)])
    ca=carry(india_g10,us10);fwd=None
    try:fwd=ccil_forward()
    except Exception as e:print('CCIL unavailable:',e,file=sys.stderr)
    fh=[x for x in (((old or {}).get('calibration') or {}).get('forward_premium_history') or []) if isinstance(x,dict) and x.get('value') is not None]
    if fwd:
        today=date.today().isoformat();fh=[x for x in fh if x.get('date')!=today];fh.append({'date':today,'value':fwd['one_month_pct']})
    fh=fh[-180:];zfwd=None;sfwd=None
    if fwd and len(fh)>=20:
        zfwd=zhist(fwd['one_month_pct'],[x['value'] for x in fh[:-1]],18,.15);sfwd=None if zfwd is None else squash(-zfwd)
    ext,_=weighted([(squash(-zo),.35),(ca.get('score'),.30),(squash(-zreer),.20),(sfwd,.15)])
    ch=None
    try:ch=china_pmi()
    except Exception as e:print('China PMI unavailable:',e,file=sys.stderr)
    rel,rh=relative_em(nifty,nifty_hist,old)
    score,cov=weighted([(gl,.30),(ext,.30),(None if not ch else ch.get('score'),.20),(rel.get('score'),.20)])
    return {'us_real_10y':float(real.value.iloc[-1]),'fed_assets_6m_pct':fed6,'usd_3m_pct':usd3,'brent_3m_pct':oil3,'vix':float(vix.value.iloc[-1]),'india_reer_bis':float(reer.value.iloc[-1]),'india_reer_z':zreer,'us_10y':ca['us_10y'],'india_us_10y_spread':ca['india_us_10y_spread'],'india_us_spread_z':ca['z'],'forward_premium_1m':None if not fwd else fwd['one_month_pct'],'forward_premium_z':zfwd,'china_pmi':ch,'relative_em':rel,'blocks':{'global_liquidity':gl,'india_external_carry':ext,'china_industrial':None if not ch else ch.get('score'),'relative_em_valuation':rel.get('score')},'score':score,'active_block_weight':cov}, {'em_ex_india_history':rh,'forward_premium_history':fh}
