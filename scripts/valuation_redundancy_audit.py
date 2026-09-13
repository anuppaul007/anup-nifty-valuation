#!/usr/bin/env python3
"""Measure redundancy among the four live V3.13 valuation lenses.

Research only. This script does NOT optimize weights, estimate expected returns,
or modify the live allocator. It evaluates the 36 fully current-definition
month-end observations already frozen in data/monthly_signal_screen.json.

The purpose is structural: quantify how much information duplication exists
because P/E enters three of the four live lenses directly or mechanically.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json, math, re
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
SCREEN=ROOT/'data'/'monthly_signal_screen.json'
MODEL=ROOT/'model.js'
OUT=ROOT/'data'/'valuation_redundancy_audit.json'

# V3.13 constants. The source-guard below fails if production changes without
# explicitly updating this diagnostic.
PE_M,PE_S=22.44,2.08
PB_M=3.54
ROE_M=16.15402934929392
BETA=.60
PB_OFFSET=.0031695843111495
PB_SCALE=.062405429030436874
DY_M,DY_S=1.25,.18
GAP_M,GAP_S=-2.60,.70
RAW_W=np.array([30.0,25.0,30.0,10.0])
LABELS=['pe_z','pb_log_profitability_z','earnings_yield_minus_gsec_z','dividend_yield_z']


def guard_model_source():
    s=MODEL.read_text(encoding='utf-8')
    required=['peM:22.44','peS:2.08','pbM:3.54','roeM:16.15402934929392','dyM:1.25','dyS:.18','gapM:-2.60','gapS:.70','wPE:30','wPB:25','wGAP:30','wDY:10','beta:.60','offset:0.0031695843111495','scale:0.062405429030436874']
    missing=[x for x in required if x not in s]
    if missing:raise RuntimeError('model_source_constants_changed: '+','.join(missing))
    m=re.search(r"const VERSION='([^']+)'",s)
    if not m:raise RuntimeError('model_version_not_found')
    return m.group(1)


def lens(row):
    pe,pb,dy,gsec=(float(row[k]) for k in ('pe','pb','dy','gsec10'))
    if min(pe,pb,dy,gsec)<=0:raise ValueError('nonpositive_input')
    pe_z=(pe-PE_M)/PE_S
    profitability=100*pb/pe
    pb_z=(math.log(pb/PB_M)-BETA*math.log(profitability/ROE_M)-PB_OFFSET)/PB_SCALE
    gap=100/pe-gsec
    gap_z=-(gap-GAP_M)/GAP_S
    dy_z=-(dy-DY_M)/DY_S
    return [pe_z,pb_z,gap_z,dy_z]


def eff_rank(eigs):
    e=np.maximum(np.asarray(eigs,dtype=float),0);p=e/e.sum()
    nz=p[p>1e-15]
    return float(math.exp(-np.sum(nz*np.log(nz))))


def round_matrix(a,n=6):return [[round(float(x),n) for x in row] for row in np.asarray(a)]


def main():
    version=guard_model_source();src=json.loads(SCREEN.read_text(encoding='utf-8'))
    rows=[r for r in src['records'] if r.get('methodology_era')=='Current ratio definitions']
    if len(rows)!=36:raise RuntimeError(f'current_definition_count_{len(rows)}_expected_36')
    x=np.asarray([lens(r) for r in rows],dtype=float)
    if not np.isfinite(x).all():raise RuntimeError('nonfinite_lens_value')
    corr=np.corrcoef(x,rowvar=False)
    eig=np.linalg.eigvalsh(corr)[::-1]
    if eig[-1] < -1e-9:raise RuntimeError('correlation_matrix_not_psd')
    condition=float(eig[0]/max(eig[-1],1e-15))
    participation=float(eig.sum()**2/np.square(eig).sum())
    erank=eff_rank(eig)
    w=RAW_W/RAW_W.sum()
    independent_var=float(w@np.eye(4)@w)
    correlated_var=float(w@corr@w)
    independent_count=float(1/independent_var)
    correlation_adjusted_count=float(1/correlated_var)
    pair=[]
    for i in range(4):
        for j in range(i+1,4):pair.append({'a':LABELS[i],'b':LABELS[j],'correlation':float(corr[i,j])})
    pair.sort(key=lambda z:abs(z['correlation']),reverse=True)
    inv=np.linalg.pinv(corr)
    vif={LABELS[i]:float(inv[i,i]) for i in range(4)}
    # Algebraic dependence map. This is exact from the production formulas,
    # independent of sample correlation.
    mechanics={
      'pe_z':['P/E'],
      'pb_log_profitability_z':['P/B','P/E through implied profitability = 100*P/B/P/E'],
      'earnings_yield_minus_gsec_z':['P/E through earnings yield = 100/P/E','government bond yield'],
      'dividend_yield_z':['dividend yield'],
      'pe_enters_lenses':3,
      'total_lenses':4,
      'pb_log_elasticity_numerator':{'log_pe':BETA,'log_pb':1-BETA}
    }
    out={
      'schema_version':1,'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
      'research_only':True,'model_version':version,'sample':{'methodology':'Current ratio definitions','months':len(rows),'first_signal_date':rows[0]['signal_date'],'last_signal_date':rows[-1]['signal_date'],'yield_caveat':src.get('yield_rule')},
      'labels':LABELS,'correlation_matrix':round_matrix(corr),'eigenvalues':[float(v) for v in eig],
      'effective_rank_entropy':erank,'effective_rank_participation':participation,'condition_number':condition,
      'pairwise_correlations':pair,'variance_inflation_factors':vif,
      'live_normalized_weights':{LABELS[i]:float(w[i]) for i in range(4)},
      'independence_geometry':{
        'effective_count_if_lenses_were_uncorrelated':independent_count,
        'correlation_adjusted_effective_count':correlation_adjusted_count,
        'weighted_variance_if_uncorrelated_unit_variance_lenses':independent_var,
        'weighted_variance_using_observed_correlation_unit_variance_lenses':correlated_var,
        'variance_inflation_due_to_observed_correlation':correlated_var/independent_var
      },
      'mechanical_dependence':mechanics,
      'interpretation_guardrail':'This is a 36-month structural redundancy diagnostic, not an alpha test, confidence interval, forecast, or basis to optimize live weights. Any covariance-aware or de-duplicated candidate must be registered as a new challenger before outcome testing.',
      'live_model_changed':False,'live_allocation_changed':False
    }
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:out[k] for k in ('sample','correlation_matrix','eigenvalues','effective_rank_entropy','effective_rank_participation','condition_number','independence_geometry','pairwise_correlations')},indent=2))

if __name__=='__main__':main()
