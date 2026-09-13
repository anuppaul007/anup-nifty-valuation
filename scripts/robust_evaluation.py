#!/usr/bin/env python3
"""Strict evidence gate for Anup Nifty Valuation.

Research only: never changes model.js or promotes parameters. Missing point-in-
time evidence is reported as not testable rather than imputed.
"""
from __future__ import annotations

from itertools import combinations
from pathlib import Path
from statistics import NormalDist
import hashlib, json, math
import numpy as np
import pandas as pd
import retrospective_core as r

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'robust_evaluation.json'
SEED=20260913
BLOCKS=(3,6,12)
DRAWS=5000
CSCV_SLICES=8
C10={'peM':22.44,'peS':2.08,'pbM':3.54,'pbS':0.3239941700435707,
     'roeM':16.15402934929392,'roeS':0.9884905234449538,'dyM':1.25,
     'dyS':.18,'gapM':-2.60,'gapS':.70,'wPE':30.,'wPB':25.,'wGAP':30.,
     'wDY':10.,'beta':.60,'k':1.35,'zc':2.5,'macroMax':6.,'earnMax':6.}


def load_json(path, default=None):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception:return default


def sha256_file(path):
    p=Path(path)
    if not p.exists():return None
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def panel_from_retrospective(data):
    if not data or data.get('status')!='complete':raise RuntimeError('data/retrospective.json unavailable')
    p=pd.DataFrame(data['records']).rename(columns={'dividend_yield':'dy'})
    p.index=pd.PeriodIndex(p.pop('month'),freq='M');r.validate_panel(p);return p


def cagr(rets):
    a=np.asarray(rets,float)
    if not len(a):return None
    wealth=float(np.prod(1+a));years=len(a)/12
    return wealth**(1/years)-1 if wealth>0 and years>0 else None


def monthly_sharpe(rets):
    a=np.asarray(rets,float)
    if len(a)<3:return None
    s=float(np.std(a,ddof=1));return float(np.mean(a)/s) if s>1e-15 else None


def t_stat(rets):
    a=np.asarray(rets,float)
    if len(a)<3:return None
    s=float(np.std(a,ddof=1));return float(np.mean(a)/(s/math.sqrt(len(a)))) if s>1e-15 else None


def net_with_weights(weights,eq,db,cost=r.COST_PER_100_TURNOVER):
    w=pd.Series(np.asarray(weights,float),index=eq.index,dtype=float)
    gross=w*eq+(1-w)*db;turn=r.rebalance_turnover(w,eq,db)
    net=(1-float(cost)*turn)*(1+gross)-1
    return pd.Series(net,index=eq.index,dtype=float),np.asarray(turn,float)


def percentile(value,sample):
    a=np.asarray(sample,float)
    if not len(a):return None
    return 100*(np.sum(a<value)+.5*np.sum(np.isclose(a,value,rtol=0,atol=1e-14)))/len(a)


def acf(x,lag):
    a=np.asarray(x,float)
    if lag<=0 or len(a)<=lag:return None
    x0,x1=a[:-lag],a[lag:]
    if np.std(x0)<=1e-15 or np.std(x1)<=1e-15:return None
    return float(np.corrcoef(x0,x1)[0,1])


def effective_sample_size(x,max_lag=12):
    a=np.asarray(x,float);n=len(a);vals={};positive=[]
    for lag in range(1,min(max_lag,max(0,n-1))+1):
        rho=acf(a,lag);vals[str(lag)]=rho
        if rho is not None and rho>0:positive.append(rho)
    design=1+2*sum(positive);neff=max(1.,min(float(n),n/design)) if n else 0
    return {'raw_n':int(n),'effective_n':float(neff),'positive_acf_sum':float(sum(positive)),
            'acf_1_to_12':vals,'method':'Bartlett-style positive-autocorrelation design effect; diagnostic only'}


def moving_block_bootstrap(diff,block,draws=DRAWS,seed=SEED):
    a=np.asarray(diff,float);n=len(a)
    if block<1 or n<block:return None
    rng=np.random.default_rng(seed+int(block));out=np.empty(draws);base=np.arange(n);need=math.ceil(n/block)
    for i in range(draws):
        parts=[]
        for s in rng.integers(0,n,size=need):
            parts.append((s+np.arange(block))%n)
        idx=np.concatenate(parts)[:n];out[i]=1200*float(np.mean(a[idx]))
    return {'block_months':int(block),'draws':int(draws),'annualized_mean_timing_pp':1200*float(np.mean(a)),
            'ci95_pp':[float(np.percentile(out,2.5)),float(np.percentile(out,97.5))],
            'probability_mean_gt_zero':float(np.mean(out>0))}


def fair_null_placebo(panel):
    frame,_,dyn,_=r.strategy_returns(panel,r.LIVE_K,r.LIVE_ZC)
    eq=frame['eq'].astype(float);db=frame['db'].astype(float);w=frame['w'].astype(float)
    mean_w=float(w.mean());static_w=pd.Series(mean_w,index=frame.index,dtype=float)
    sta,sta_turn=net_with_weights(static_w,eq,db);timing=dyn-sta
    dyn_c=float(cagr(dyn));sta_c=float(cagr(sta));edge=100*(dyn_c-sta_c)
    wa=w.to_numpy(float);placebos=[]
    for shift in range(1,len(wa)):
        pn,pt=net_with_weights(np.roll(wa,shift),eq,db)
        placebos.append((100*float(cagr(pn)-sta_c),float(pt.sum())))
    px=[x[0] for x in placebos]
    return {'months':int(len(frame)),'mean_equity_pct':100*mean_w,
      'dynamic_net':r.stats(dyn.to_numpy(),w.to_numpy(),True),
      'beta_matched_static_net':r.stats(sta.to_numpy(),static_w.to_numpy(),True),
      'dynamic_minus_static_cagr_pp':float(edge),'net_timing_mean_annualized_pp':1200*float(timing.mean()),
      'net_timing_t_stat_naive':t_stat(timing),'timing_effective_sample':effective_sample_size(timing),
      'signal_weight_lag1_autocorrelation':acf(w,1),'dynamic_realised_turnover_x':float(frame['turnover'].sum()),
      'static_realised_turnover_x':float(sta_turn.sum()),
      'placebo':{'method':'all non-zero circular shifts of exact target weights','unique_paths':len(placebos),
                 'actual_percentile':float(percentile(edge,px)),'p05_excess_cagr_pp':float(np.percentile(px,5)),
                 'median_excess_cagr_pp':float(np.percentile(px,50)),'p95_excess_cagr_pp':float(np.percentile(px,95)),
                 'max_excess_cagr_pp':float(np.max(px))},
      'paired_moving_block_bootstrap':[moving_block_bootstrap(timing,b) for b in BLOCKS]}


def variant_matrix(panel):
    d={}
    for zc in r.EXTREMES:
        for k in r.CURVES:
            f,_,net,_=r.strategy_returns(panel,k,zc);d[r.grid_key(k,zc)]=pd.Series(net,index=f.index,dtype=float)
    m=pd.DataFrame(d).dropna()
    if len(m)<24 or m.shape[1]!=24:raise RuntimeError(f'variant matrix incomplete: {m.shape}')
    return m


def deflated_sharpe_probability(rets,benchmark_sr):
    a=np.asarray(rets,float);sr=monthly_sharpe(a)
    if sr is None or len(a)<4:return None
    s=pd.Series(a);skew=float(s.skew());kurt=float(s.kurt())+3
    den2=1-skew*sr+((kurt-1)/4)*sr*sr
    if den2<=0:return None
    z=(sr-benchmark_sr)*math.sqrt(len(a)-1)/math.sqrt(den2)
    return {'monthly_sharpe':float(sr),'benchmark_expected_max_monthly_sharpe':float(benchmark_sr),
            'probability':float(NormalDist().cdf(z)),'z':float(z),'skew':skew,'raw_kurtosis':kurt}


def multiple_testing(panel):
    m=variant_matrix(panel);sharpes={k:monthly_sharpe(m[k]) for k in m.columns}
    vals=np.asarray(list(sharpes.values()),float);ntr=len(vals);sd=float(np.std(vals,ddof=1));nd=NormalDist();gamma=.5772156649015329
    expected=sd*((1-gamma)*nd.inv_cdf(1-1/ntr)+gamma*nd.inv_cdf(1-1/(ntr*math.e))) if sd>0 else 0
    live=r.grid_key(r.LIVE_K,r.LIVE_ZC);best=max(sharpes,key=sharpes.get)
    arr=m.to_numpy(float);T,N=arr.shape;slices=np.array_split(np.arange(T),CSCV_SLICES);logits=[];selected={}
    for ins_tuple in combinations(range(CSCV_SLICES),CSCV_SLICES//2):
        ins=set(ins_tuple);tr=np.concatenate([slices[i] for i in range(CSCV_SLICES) if i in ins]);te=np.concatenate([slices[i] for i in range(CSCV_SLICES) if i not in ins])
        trsr=np.array([monthly_sharpe(arr[tr,j]) for j in range(N)],float);tesr=np.array([monthly_sharpe(arr[te,j]) for j in range(N)],float)
        win=int(np.nanargmax(trsr));name=m.columns[win];selected[name]=selected.get(name,0)+1;target=tesr[win]
        rank=1+np.sum(tesr<target)+.5*max(0,np.sum(np.isclose(tesr,target,rtol=0,atol=1e-14))-1)
        omega=min(max(float(rank)/(N+1),1e-12),1-1e-12);logits.append(math.log(omega/(1-omega)))
    return {'candidate_family':'24-member valuation curve grid','trial_count':int(ntr),'variant_months':int(T),
      'monthly_sharpe_std_across_trials':sd,'expected_max_monthly_sharpe_under_selection':float(expected),
      'live_variant':{'key':live,**(deflated_sharpe_probability(m[live],expected) or {})},
      'best_observed_variant':{'key':best,**(deflated_sharpe_probability(m[best],expected) or {})},
      'cscv':{'slices':CSCV_SLICES,'splits':len(logits),'pbo':float(np.mean(np.asarray(logits)<=0)),
              'median_oos_rank_logit':float(np.median(logits)),'in_sample_winner_counts':selected},
      'warning':'DSR/PBO apply only to this exact common candidate family; other research families are logged separately.'}


def lens_redundancy(panel):
    c=r.C;rows=[]
    for _,x in panel.iterrows():
        pe,pb,dy,g=map(float,(x.pe,x.pb,x.dy,x.gsec10));roe=100*pb/pe;gap=100/pe-g
        rows.append([(pe-c['peM'])/c['peS'],(pb-c['pbM'])/c['pbS']-c['beta']*(roe-c['roeM'])/c['roeS'],-(gap-c['gapM'])/c['gapS'],-(dy-c['dyM'])/c['dyS']])
    names=['pe','pb_profitability_adjusted','earnings_yield_minus_gsec','dividend_yield'];df=pd.DataFrame(rows,index=panel.index,columns=names)
    corr=df.corr().to_numpy(float);eig=np.clip(np.linalg.eigvalsh(corr),0,None);eff=float(eig.sum()**2/np.square(eig).sum())
    off=corr.copy();np.fill_diagonal(off,np.nan)
    return {'months':len(df),'correlation_matrix':{names[i]:{names[j]:float(corr[i,j]) for j in range(4)} for i in range(4)},
            'eigenvalues':[float(v) for v in eig],'effective_independent_lenses':eff,
            'max_absolute_pairwise_correlation':float(np.nanmax(np.abs(off))),
            'interpretation':'Displayed lenses are correlated; participation ratio estimates effective independent dimensions.'}


def curve10(z):
    f=lambda x:100/(1+math.exp(C10['k']*x));lo=f(C10['zc']);hi=f(-C10['zc']);return max(0,min(100,(f(z)-lo)/(hi-lo)*100))


def fair_pe_fan(latest):
    if not latest or latest.get('model_version')!='3.10-pb-regime-1':return {'status':'unavailable','reason':'model version mismatch'}
    n=latest.get('nifty',{});en=latest.get('earnings',{});ma=latest.get('macro',{})
    req=[n.get('pe'),n.get('pb'),n.get('div_yield'),n.get('gsec10'),en.get('score'),ma.get('score')]
    if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in req):return {'status':'unavailable','reason':'missing numeric inputs'}
    pe,pb,dy,g=map(float,req[:4]);roe=100*pb/pe;gap=100/pe-g;rows=[];tw=C10['wPE']+C10['wPB']+C10['wGAP']+C10['wDY']
    for pref in range(18,27):
        zp=(pe-pref)/C10['peS'];zb=(pb-C10['pbM'])/C10['pbS']-C10['beta']*(roe-C10['roeM'])/C10['roeS'];zg=-(gap-C10['gapM'])/C10['gapS'];zd=-(dy-C10['dyM'])/C10['dyS']
        z=(C10['wPE']*zp+C10['wPB']*zb+C10['wGAP']*zg+C10['wDY']*zd)/tw;core=curve10(z);damp=max(0,min(1,1-abs(z)/C10['zc']))
        final=max(0,min(100,core+max(-1,min(1,float(en['score'])))*C10['earnMax']*damp+max(-1,min(1,float(ma['score'])))*C10['macroMax']*damp))
        rows.append({'assumed_fair_pe':pref,'valuation_z':float(z),'core_equity_pct':float(core),'mechanical_full_equity_pct':float(final)})
    vals=[q['mechanical_full_equity_pct'] for q in rows]
    return {'status':'complete','current_nifty_pe':pe,'fan':rows,'equity_range_pct':[float(min(vals)),float(max(vals))],'spread_pp':float(max(vals)-min(vals)),
            'note':'One-at-a-time fair-P/E sensitivity; all other V3.10 references and current inputs held fixed.'}


def calibration_sensitivity(data):
    if not data or data.get('status')!='complete':return {'status':'unavailable'}
    cw=data.get('common_window',{});keys=['fixed_reference_live_curve','fixed_reference_yield_lag_2m','rolling_36m_equal_lenses','expanding_equal_lenses'];rows={}
    for k in keys:
        if k in cw:rows[k]={x:cw[k].get(x) for x in ('months','cagr_pct','max_drawdown_pct','annual_vol_pct','annual_turnover_x','first_signal','last_signal')}
    return {'status':'complete' if rows else 'unavailable','common_window_methods':rows,
            'warning':'Rolling/expanding use prior observations but were designed retrospectively; no untouched OOS claim.'}


def crash_challenger(trend):
    if not trend or not trend.get('conclusion'):return {'status':'unavailable'}
    ref=trend.get('reference_variant',{});gate=trend.get('frozen_gate_assessment',{});delta=ref.get('delta',{})
    return {'status':'complete','policy_id':trend.get('policy_id'),'conclusion':trend.get('conclusion'),
      'max_drawdown_improvement_pp':delta.get('max_drawdown_improvement_pp'),'cagr_delta_pp':delta.get('cagr_delta_pp'),
      'covid_drawdown_improvement_pp':trend.get('stress_reference',{}).get('covid',{}).get('improvement_pp'),
      'historical_gate_drawdown_requirement_met':gate.get('drawdown_requirement_met'),
      'historical_result_can_promote_live':gate.get('historical_result_can_promote_live')}


def track_record_heuristic(weight_rho1,delta_sharpe=.20):
    rho=float(weight_rho1) if weight_rho1 is not None and math.isfinite(float(weight_rho1)) else 0.;rho=max(0,min(.99,rho));design=(1+rho)/(1-rho)
    n95=(1.959963984540054/delta_sharpe)**2;n80=((1.959963984540054+.8416212335729143)/delta_sharpe)**2
    return {'target_sharpe_difference':delta_sharpe,'independent_observations_for_95pct_signal_to_noise':float(n95),
      'independent_observations_for_95pct_two_sided_80pct_power':float(n80),'observed_weight_lag1_rho':rho,'ar1_design_effect':float(design),
      'approx_calendar_months_95pct':math.ceil(n95*design),'approx_calendar_years_95pct':float(n95*design/12),
      'approx_calendar_months_80pct_power':math.ceil(n80*design),'approx_calendar_years_80pct_power':float(n80*design/12),
      'warning':'Heuristic illustrating persistence cost; not a substitute for a full power model.'}


def prospective_count():
    p=ROOT/'data'/'evidence'/'decisions';return len(list(p.glob('*.json'))) if p.exists() else 0


def build():
    retro=load_json(ROOT/'data'/'retrospective.json');panel=panel_from_retrospective(retro);fair=fair_null_placebo(panel);multi=multiple_testing(panel)
    policy=load_json(ROOT/'robust_evaluation_policy.json',{});thr=policy.get('promotion_evidence_thresholds',{});pros=prospective_count()
    boots=fair['paired_moving_block_bootstrap'];gates={
      'exposure_matched_timing_edge_positive':fair['dynamic_minus_static_cagr_pp']>0,
      'placebo_95th_percentile':fair['placebo']['actual_percentile']>=thr.get('placebo_percentile_min',95),
      'paired_block_bootstrap_all_lower_bounds_above_zero':all(q and q['ci95_pp'][0]>0 for q in boots),
      'deflated_sharpe_probability':multi['live_variant'].get('probability',0)>=thr.get('deflated_sharpe_probability_min',.95),
      'cscv_pbo':multi['cscv']['pbo']<=thr.get('pbo_max',.10),
      'prospective_months':pros>=thr.get('prospective_completed_months_min',60),
      'certified_point_in_time_full_stack_history':False,
      'taxable_after_tax_implementation_test':False}
    files=[ROOT/'model.js',ROOT/'data'/'retrospective.json',ROOT/'data'/'latest.json',ROOT/'validation_policy.json',ROOT/'robust_evaluation_policy.json',ROOT/'research_trial_registry.json',ROOT/'release_timing_policy.json']
    return {'schema_version':1,'status':'complete','scope':'Valuation-core robust evaluation plus separately governed current sensitivities/challengers; not a certified historical full-stack V3.10 backtest.',
      'decision':'ELIGIBLE_FOR_SEPARATE_PROMOTION_REVIEW' if all(gates.values()) else 'NOT_ELIGIBLE_FOR_PROMOTION',
      'decision_reason':'Every critical gate must pass; no composite score averages away failures.',
      'fair_null_and_timing':fair,'multiple_testing_and_overfit':multi,'sample_size':track_record_heuristic(fair['signal_weight_lag1_autocorrelation']),
      'lens_redundancy':lens_redundancy(panel),'fair_pe_reference_sensitivity':fair_pe_fan(load_json(ROOT/'data'/'latest.json')),
      'calibration_sensitivity':calibration_sensitivity(load_json(ROOT/'data'/'robustness.json')),'crash_challenger':crash_challenger(load_json(ROOT/'data'/'trend_challenger_summary.json')),
      'prospective_evidence':{'completed_decision_files':pros,'minimum_required_before_any_promotion_review':thr.get('prospective_completed_months_min',60)},
      'implementation_status':{'transaction_costs':'10 bp one-way in core timing audit; cost sensitivities elsewhere','taxes':'NOT TESTED; no taxable-investor net claim','full_stack_release_vintages':'NOT TESTABLE until available_at history satisfies release_timing_policy.json'},
      'trial_registry':load_json(ROOT/'research_trial_registry.json',{}),'gate_matrix':gates,
      'reproducibility':{'hash_algorithm':'sha256','files':{str(p.relative_to(ROOT)):sha256_file(p) for p in files}},
      'governance':'No output changes live parameters automatically. Failed/unavailable gates remain visible and cannot be neutral-filled.'}


def main():
    try:out=build()
    except Exception as e:out={'schema_version':1,'status':'unavailable','decision':'NOT_ELIGIBLE_FOR_PROMOTION','error':f'{type(e).__name__}: {e}','governance':'Evaluation failure cannot promote or alter live model.'}
    OUT.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'status':out.get('status'),'decision':out.get('decision'),'months':out.get('fair_null_and_timing',{}).get('months'),'placebo_percentile':out.get('fair_null_and_timing',{}).get('placebo',{}).get('actual_percentile'),'dsr_probability':out.get('multiple_testing_and_overfit',{}).get('live_variant',{}).get('probability'),'pbo':out.get('multiple_testing_and_overfit',{}).get('cscv',{}).get('pbo'),'error':out.get('error')},separators=(',',':')))

if __name__=='__main__':main()
