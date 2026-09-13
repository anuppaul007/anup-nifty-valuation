#!/usr/bin/env python3
"""Audit the macro overlay as a decision, not as a collection of indicators.

The audit deliberately refuses to manufacture a historical macro P&L from
current-vintage series. If certified point-in-time/release-vintage outcomes do
not exist, the economic price of active macro authority is reported as
unavailable rather than backfilled.

It also separates observable pipeline failures from the latent probability of a
wrong-but-plausible semantic source error. The latter is not identifiable from
a handful of caught incidents and therefore is never converted into a fake
monthly probability.
"""
from __future__ import annotations

from pathlib import Path
import json
import math
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'macro_authority_audit.json'
LATEST=ROOT/'data'/'latest.json'
DECISIONS=ROOT/'data'/'evidence'/'decisions'


def finite(x):
    try:return x is not None and math.isfinite(float(x))
    except (TypeError,ValueError):return False


def live_model_result(packet):
    program=(
      "const M=require('./model.js'),fs=require('fs');"
      "const d=JSON.parse(fs.readFileSync(0,'utf8'));"
      "const r=M.calculate(d);"
      "process.stdout.write(JSON.stringify({version:M.VERSION,C:M.C,r}));"
    )
    p=subprocess.run(['node','-e',program],cwd=ROOT,input=json.dumps(packet,allow_nan=False),text=True,capture_output=True,check=True)
    return json.loads(p.stdout)


def prospective_decisions():
    rows=[]
    if DECISIONS.exists():
        for p in sorted(DECISIONS.glob('*.json')):
            try:
                d=json.loads(p.read_text(encoding='utf-8'))
                rows.append({'month':d.get('month'),'first_seen_at':d.get('first_seen_at'),'equity_pct':d.get('equity_pct'),'model_version':d.get('model_version')})
            except Exception:
                continue
    return rows


def factor_surface(macro):
    factors=macro.get('factors') or {}
    active=[k for k,v in factors.items() if isinstance(v,dict) and v.get('display_only') is not True]
    display=[k for k,v in factors.items() if isinstance(v,dict) and v.get('display_only') is True]
    dom=((macro.get('domestic') or {}).get('factors') or {})
    raw=len(active)+len(dom)
    ch=macro.get('china_pmi') or {}
    china_raw=sum(int(finite(ch.get(k))) for k in ('pmi','new_orders'))
    raw+=china_raw
    # China PMI/new orders are compressed into one scored China block/node.
    scored_nodes=len(active)+len(dom)+(1 if china_raw else 0)
    blocks=sum(int(finite(v)) for k,v in (macro.get('blocks') or {}).items() if k in {'global_liquidity','india_external_carry','india_domestic','china_industrial'})
    return {
      'top_level_blocks':blocks,
      'scored_factor_nodes':scored_nodes,
      'raw_scored_indicators':raw,
      'display_only_factor_count':len(display),
      'active_factor_keys':active,
      'domestic_factor_keys':sorted(dom.keys()),
      'display_only_factor_keys':display,
      'china_raw_indicators':['pmi','new_orders'] if china_raw==2 else ['partial_or_missing'],
    }


def main():
    packet=json.loads(LATEST.read_text(encoding='utf-8'))
    model=live_model_result(packet);r=model['r'];C=model['C'];m=packet.get('macro') or {}
    decisions=prospective_decisions()
    audit_text=(ROOT/'AUDIT.md').read_text(encoding='utf-8') if (ROOT/'AUDIT.md').exists() else ''
    known=[]
    if 'wrong STOXX table binding' in audit_text:
        known.append({'incident':'Wrong STOXX table binding read a non-fundamental table as fundamentals','status':'caught_and_fixed','scope':'historical project audit; demonstrates semantic parser risk'})
    current_live=float(r.get('ma') or 0.0) if r.get('macroEligible') else 0.0
    shadow=r.get('macroShadowAdjustment')
    if not finite(shadow) and r.get('macroEligible') and finite(m.get('score')):
        shadow=float(m['score'])*float(C.get('macroShadowMax',C.get('macroMax',0)))*float(r.get('damp',1))
    surface=factor_surface(m)
    out={
      'schema_version':1,
      'status':'complete',
      'model_version':model['version'],
      'current_snapshot':{
        'generated_at':packet.get('generated_at'),
        'macro_score':m.get('score'),
        'macro_context_eligible':bool(r.get('macroEligible')),
        'live_macro_adjustment_pp':current_live,
        'shadow_macro_adjustment_pp':float(shadow) if finite(shadow) else None,
        'live_macro_budget_pp':float(C.get('macroMax',0)),
        'shadow_macro_budget_pp':float(C.get('macroShadowMax',C.get('macroMax',0))),
      },
      'pipeline_surface':surface,
      'prospective_evidence':{
        'archived_monthly_decisions':len(decisions),
        'decisions':decisions,
        'realized_monthly_outcomes_available_for_macro_ablation':0,
        'status':'insufficient_to_price_return_or_drawdown_effect',
      },
      'historical_economic_pricing':{
        'status':'unavailable',
        'cagr_added_or_cost_pp_per_year':None,
        'max_drawdown_avoided_or_added_pp':None,
        'reason':'The project has no certified release-vintage historical reconstruction of the full macro stack on the live allocation sample. Current-vintage backfilling would answer a different question and is not substituted.',
      },
      'operational_risk':{
        'known_semantic_incidents':known,
        'wrong_but_plausible_monthly_probability':None,
        'probability_status':'not_identifiable_from_available_evidence',
        'reason':'Caught parser/source incidents have no defensible denominator for latent silent semantic errors. Missing/stale/inconsistent inputs are fail-closed, but a syntactically valid wrong table or changed source meaning is a different failure class.',
      },
      'governance_recommendation':{
        'decision':'live_budget_zero_context_only_until_priced',
        'recommended_live_macro_budget_pp':0,
        'retain_shadow_budget_pp':6,
        'rationale':'Active macro authority has no auditable historical return/drawdown price and a non-trivial semantic source surface. Preserve the verified blocks as displayed context and a prospective ±6pp shadow challenger, but do not let macro change or withhold the live allocation until decision value is demonstrated.',
        'promotion_requirement':'At minimum, a predeclared prospective or certified release-vintage macro-on versus macro-off comparison with identical valuation/earnings/trend inputs, costs and outcome dates. Any tested alternative macro budget joins its comparable selection family.',
      },
      'limitations':[
        'This audit does not estimate an unobservable silent-error probability from anecdotal incidents.',
        'It does not backfill macro history from revised/current-vintage economic series.',
        'It does not test 3/6/9/12/15pp alternatives or select a winning macro budget.',
        'The current snapshot contribution is an allocation delta, not evidence of investment value.'
      ]
    }
    OUT.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({
      'model_version':out['model_version'],
      'current':out['current_snapshot'],
      'surface':surface,
      'prospective_decisions':len(decisions),
      'historical_pricing':out['historical_economic_pricing']['status'],
      'silent_probability':out['operational_risk']['probability_status'],
      'recommendation':out['governance_recommendation']['decision'],
    },separators=(',',':')))


if __name__=='__main__':main()
