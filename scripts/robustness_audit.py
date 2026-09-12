"""Reproducible research, never a parameter optimizer or full macro backtest."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import retrospective_core as r
ROOT=Path(__file__).resolve().parents[1]

def calibrated_weights(panel,window=None):
    # Reference distributions end BEFORE the signal month. Current-vintage
    # bond history is lagged two calendar months as a publication-lag sensitivity.
    p=panel.copy();p['gsec10']=p.gsec10.shift(2)
    lenses=pd.DataFrame({'pe':p.pe,'pb':p.pb,'gap':-(100/p.pe-p.gsec10),'dy':-p.dy})
    weights=pd.Series(np.nan,index=p.index)
    for i in range(36,len(p)):
        prior=lenses.iloc[max(0,i-window) if window else 0:i].dropna()
        if len(prior)<34:continue
        median=prior.median();scale=1.4826*(prior-median).abs().median()
        if (scale<=1e-8).any():continue
        z=((lenses.iloc[i]-median)/scale).clip(-3,3).mean()
        weights.iloc[i]=r.curve(z)/100
    return weights

def performance(panel,weights,cost=.001):
    eq=panel.equity_tri.pct_change().shift(-1);db=panel.debt_tri.pct_change().shift(-1)
    f=pd.DataFrame({'w':weights,'eq':eq,'db':db}).dropna()
    gross=f.w*f['eq']+(1-f.w)*f.db
    turn=r.rebalance_turnover(f.w,f['eq'],f.db)
    net=(1-cost*turn)*(1+gross)-1
    return dict(r.stats(net,f.w,True),annual_turnover_x=float(sum(turn)/(len(f)/12)),first_signal=str(f.index[0]),last_signal=str(f.index[-1]))

def build(data):
    p=pd.DataFrame(data['records']).rename(columns={'dividend_yield':'dy'})
    p.index=pd.PeriodIndex(p.pop('month'),freq='M');r.validate_panel(p)
    rolling=calibrated_weights(p,36);expanding=calibrated_weights(p)
    common=rolling.notna()&expanding.notna()
    lag=p.copy();lag['gsec10']=p.gsec10.shift(2)
    fixed=p.apply(r.valuation_z,axis=1).map(lambda z:r.curve(z)/100)
    lagged=lag.apply(lambda row:r.curve(r.valuation_z(row))/100 if pd.notna(row.gsec10) else np.nan,axis=1)
    weights={'fixed_reference_live_curve':fixed,'fixed_reference_yield_lag_2m':lagged,'rolling_36m_equal_lenses':rolling,'expanding_equal_lenses':expanding,
             'fixed_60_40':pd.Series(.6,index=p.index),'fixed_70_30':pd.Series(.7,index=p.index),'equity_100':pd.Series(1.,index=p.index)}
    results={k:performance(p,w.where(common)) for k,w in weights.items()}
    full={k:performance(p,w) for k,w in weights.items() if not k.startswith(('rolling','expanding'))}
    return {'status':'complete','source_study':'data/retrospective.json','asof':str(p.index[-1]),'method_version':'3.7',
      'scope':'Valuation core only. Macro and earnings strategy performance is NOT tested.',
      'limitations':['Current-vintage histories, not archived releases; a two-month yield lag is sensitivity, not proof of historical availability.',
      'Rolling/expanding use earlier observations only, but the design was chosen retrospectively. No claim of untouched out-of-sample performance.',
      'Equal lens weights are a research alternative; P/E and earnings yield remain correlated.',
      'Monthly drawdowns miss intramonth losses. Debt is a long-duration government-bond index, not cash or risk-free return.',
      '10 bps per one-way turnover, charged before returns, on dynamic and fixed monthly-rebalanced portfolios. Initial acquisition and taxes excluded.',
      'The short comparable era omits the 2008 crash and March 2020 crash. No maximum-return claim is supported.'],
      'common_window':results,'full_window_fixed_references':full,
      'cost_sensitivity_live':{str(c):performance(p,fixed,c) for c in [0,.001,.005]},
      'automatic_parameter_change':False}

if __name__=='__main__':
    try:
        data=json.loads((ROOT/'data/retrospective.json').read_text())
        if data.get('status')!='complete':raise RuntimeError('Retrospective panel unavailable')
        out=build(data)
    except Exception as error:
        out={'status':'unavailable','error':str(error),'automatic_parameter_change':False}
    (ROOT/'data/robustness.json').write_text(json.dumps(out,indent=2,allow_nan=False))
    print(json.dumps({'status':out['status'],'asof':out.get('asof'),'error':out.get('error')}))
