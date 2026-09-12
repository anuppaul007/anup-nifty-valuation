"""First-of-month valuation-core reconstruction, not historical macro advice."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date,datetime,timezone
from pathlib import Path
import json
import pandas as pd
import update_data as b
import macro_v3 as m
import retrospective_core as model

ROOT=Path(__file__).resolve().parents[1]
YIELD_URL=('https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0/IND.M.IRLT.PA.....?startPeriod=1999-01&dimensionAtObservation=AllDimensions&format=csvfile')

def fetch_year(year):
    from jugaad_data.nse import index_pe_raw
    rows=index_pe_raw('NIFTY 50',date(year,1,1),min(date(year,12,31),date.today()))
    out=[]
    for row in rows or []:
        dt=b.pdate(b.pick(row,['Date','DATE','HistoricalDate']))
        vals=[b.fnum(b.pick(row,aliases)) for aliases in [['P/E','PE','pe'],['P/B','PB','pb'],['Div Yield %','Div Yield','Dividend Yield','DY','divYield']]]
        if dt and all(m.finite(x) and x>0 for x in vals):out.append({'date':dt.isoformat(),'pe':vals[0],'pb':vals[1],'dy':vals[2]})
    print(json.dumps({'year':year,'valid_rows':len(out)}),flush=True)
    return out

def reconstruct(ratios,yields,end):
    records=[]
    for stamp in pd.date_range('2000-01-01',end,freq='MS'):
        signal=stamp.date();eligible=[r for r in ratios if r['date']<signal.isoformat()]
        row={'signal_date':signal.isoformat(),'full_model_equity':None,'full_model_status':'Not reconstructable: historical macro/earnings releases unavailable'}
        if not eligible:row['status']='Missing prior NIFTY observation';records.append(row);continue
        n=max(eligible,key=lambda r:r['date']);row.update(nifty_asof=n['date'],pe=n['pe'],pb=n['pb'],dy=n['dy'])
        # Two calendar-month lag; release-vintage dates are not available.
        cutoff=str(stamp.to_period('M')-2)
        y=yields[yields.date.dt.to_period('M').astype(str)<=cutoff]
        if y.empty:row['status']='Missing prior India yield';records.append(row);continue
        yy=y.iloc[-1];row.update(gsec_asof=yy.date.date().isoformat(),gsec10=float(yy.value))
        if (signal-date.fromisoformat(n['date'])).days>7 or (signal-yy.date.date()).days>100:
            row['status']='Input exceeds age limit';records.append(row);continue
        zz=model.valuation_z(pd.Series(dict(pe=n['pe'],pb=n['pb'],dy=n['dy'],gsec10=float(yy.value))))
        core=model.curve(zz);damp=max(0,min(1,1-abs(zz)/2.5));lo=max(0,core-12*damp);hi=min(100,core+12*damp)
        row.update(status='Valuation-core reconstruction',methodology_era='Pre-change: non-comparable' if n['date']<'2021-03-31' else 'Current-methodology era',z=zz,core_equity=core,core_debt=100-core,
                   equity_above_80=core>80,debt_above_80=(100-core)>80,full_overlay_lower_bound=lo,full_overlay_upper_bound=hi,
                   equity_above_80_all_overlay_scores=lo>80,debt_above_80_all_overlay_scores=hi<20)
        records.append(row)
    return records

def main():
    parts=[];errors=[]
    def safe_year(y):
        try:return fetch_year(y)
        except Exception as e:errors.append({'year':y,'error':str(e)});return []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for q in pool.map(safe_year,range(1999,date.today().year+1)):parts.extend(q)
    by={r['date']:r for r in parts};ratios=sorted(by.values(),key=lambda r:r['date'])
    yields=m._sdmx_csv(YIELD_URL,YIELD_URL)
    records=reconstruct(ratios,yields,date.today())
    out={'generated_at':datetime.now(timezone.utc).isoformat(),'scope':'Current fixed-reference valuation core only. No historical full-macro allocation is claimed.',
         'decision_rule':'1st of each calendar month; most recent NIFTY observation strictly before that date, age <=7 days.',
         'yield_rule':'Latest OECD monthly India long-term yield for a period at least two months before the decision month, age <=100 days. Publication-lag sensitivity, not verified release-vintage history.',
         'threshold_rule':'Strictly greater than 80%, based on unrounded allocations. Debt >80% means equity <20%.',
         'source_urls':['https://www.niftyindices.com/reports/historical-data',YIELD_URL],
         'model_parameters':dict(model.C,k=model.LIVE_K,zc=model.LIVE_ZC,wPE=30,wPB=25,wGAP=30,wDY=10),
         'source_errors':errors,'raw_ratio_count':len(ratios),'first_ratio':ratios[0]['date'] if ratios else None,
         'first_yield':yields.date.iloc[0].date().isoformat(),'last_yield':yields.date.iloc[-1].date().isoformat(),
         'records':records}
    target=ROOT/'research/monthly_extremes.json';target.parent.mkdir(exist_ok=True);target.write_text(json.dumps(out,indent=2,allow_nan=False))
    print(json.dumps({'months':len(records),'computed':sum('core_equity' in r for r in records),'equity_above_80':sum(r.get('equity_above_80',False) for r in records),'debt_above_80':sum(r.get('debt_above_80',False) for r in records),'source_errors':errors}),flush=True)
if __name__=='__main__':main()
