"""Primary-source adapters shared by the next model and its source verification."""
from datetime import date
from io import StringIO
import re
import pandas as pd
from lxml import etree,html
import http_client as http
import macro_v3 as m

RBI_NSDP='https://www.rbi.org.in/scripts/BS_NSDPDisplay.aspx'

def bis_series(flow,key):
    url=f'https://stats.bis.org/api/v1/data/{flow}/{key}?startPeriod=2000-01&format=csv'
    r=http.get(url,headers={'Accept':'text/csv','User-Agent':m.UA['User-Agent']},timeout=30)
    r.raise_for_status()
    if r.text.lstrip().startswith('<'):
        tree=etree.fromstring(r.content)
        pts=[]
        for obs in tree.xpath('//*[local-name()="Obs"]'):
            dt=obs.get('TIME_PERIOD');value=obs.get('OBS_VALUE')
            if dt is None:
                ds=obs.xpath('./*[local-name()="ObsDimension"]/@value')
                vs=obs.xpath('./*[local-name()="ObsValue"]/@value')
                if ds and vs:dt,value=ds[0],vs[0]
            if dt is not None and value is not None:pts.append((dt,value))
        q=pd.DataFrame(pts,columns=['date','value'])
    else:
        t=pd.read_csv(StringIO(r.text))
        def col(name):return next(c for c in t.columns if str(c).split(':')[0].strip().upper()==name)
        if 'REF_AREA' in [str(c).split(':')[0].strip().upper() for c in t.columns]:
            t=t[t[col('REF_AREA')].astype(str).str.split(':').str[0].eq('IN')]
        q=pd.DataFrame({'date':t[col('TIME_PERIOD')],'value':t[col('OBS_VALUE')]})
    # A single-series request must not silently merge different measures.
    if q.empty or q['date'].duplicated().any():raise RuntimeError('BIS series is absent or ambiguous')
    return m.clean(q,url)

def parse_rbi_financials(text):
    page=' '.join(html.fromstring(text).text_content().split())
    stamp=r'([A-Za-z]+/\d{1,2}/\d{4})'
    number=r'(-?[\d,]+(?:\.\d+)?)'
    def record(pattern,unit,change=False):
        hit=re.search(pattern,page,re.I)
        if not hit:raise RuntimeError('RBI row not found: '+pattern[:60])
        dt=pd.to_datetime(hit[1],format='%B/%d/%Y').date().isoformat()
        out={'value':float(hit[2].replace(',','')),'asof':dt,'source_url':RBI_NSDP,'unit':unit}
        if change:out['growth_yoy']=float(hit[4].replace(',',''))
        return out
    out={}
    out['forward_1m']=record(r'1-month\s+Per cent per annum\s+'+stamp+r'\s+'+number,'% annualized')
    out['forward_3m']=record(r'3-month\s+Per cent per annum\s+'+stamp+r'\s+'+number,'% annualized')
    out['forward_6m']=record(r'6-month\s+Per cent per annum\s+'+stamp+r'\s+'+number,'% annualized')
    for key,label in [('m3',r'Broad Money \(M3\)'),('credit','Other Domestic Credit')]:
        out[key]=record(label+r'\s+₹\s*Billion\s+'+stamp+r'\s+'+number+r'\s+'+number+r'\s+'+number,'INR billion',True)
    return out

def rbi_financials():
    r=http.get(RBI_NSDP,headers=m.UA,timeout=30);r.raise_for_status()
    return parse_rbi_financials(r.text)

def records(df):
    return [[str(row.date.date()),float(row.value)] for row in df.itertuples()]
