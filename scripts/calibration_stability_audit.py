#!/usr/bin/env python3
"""V3.13 calibration fragility audit.

Research only. No return series is read. The audit asks how sensitive today's
allocation is to the short 36-month current-definition calibration window.
It applies deterministic descriptive recalibrations (median + population SD)
to the same four raw lens quantities, then omits each contiguous six-month
block in turn. These are sensitivity scenarios, NOT alternative fair values,
confidence intervals, or candidates for automatic promotion.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, math, re, sys
import numpy as np
from calibration_anchor_guard import validate_anchor, write_report, write_withheld, verify_publication, enforce_reproduction, validate_provenance

ROOT=Path(__file__).resolve().parents[1]
SCREEN=ROOT/'data'/'monthly_signal_screen.json'
LATEST=ROOT/'data'/'latest.json'
RELIABILITY=ROOT/'data'/'reliability_audit.json'
MODEL=ROOT/'model.js'
OUT=ROOT/'data'/'calibration_stability_audit.json'

PE_M,PE_S=22.44,2.08
PB_M=3.54
ROE_M=16.15402934929392
BETA=.60
PB_OFFSET=.0031695843111495
PB_SCALE=.062405429030436874
DY_M,DY_S=1.25,.18
GAP_M,GAP_S=-2.60,.70
K,ZC=1.35,2.5
EARN_MAX,TREND_PP=6.0,20.0
W=np.array([30.0,25.0,30.0,10.0]);W=W/W.sum()
LABELS=['pe','pb_log_profitability','earnings_yield_minus_gsec','dividend_yield']


def guard_model_source():
    s=MODEL.read_text(encoding='utf-8')
    required=['peM:22.44','peS:2.08','pbM:3.54','roeM:16.15402934929392','dyM:1.25','dyS:.18','gapM:-2.60','gapS:.70','k:1.35','zc:2.5','earnMax:6','trendRiskOffPP:20','offset:0.0031695843111495','scale:0.062405429030436874']
    missing=[x for x in required if x not in s]
    if missing:raise RuntimeError('model_source_constants_changed: '+','.join(missing))
    m=re.search(r"const VERSION='([^']+)'",s)
    if not m:raise RuntimeError('model_version_not_found')
    return m.group(1)


def raw_vector(pe,pb,dy,gsec):
    pe,pb,dy,gsec=map(float,(pe,pb,dy,gsec))
    if not all(math.isfinite(v) and v > 0 for v in (pe,pb,dy,gsec)):
        raise ValueError('nonfinite_or_nonpositive_input')
    roe=100*pb/pe
    # Individually finite inputs can overflow in derived ratios (e.g. ROE).
    # Reject the derived nonfinite state before it contaminates calibration.
    if not math.isfinite(roe) or roe <= 0:
        raise ValueError('nonfinite_derived_input')
    vector=np.array([pe,math.log(pb)-BETA*math.log(roe),100/pe-gsec,dy],dtype=float)
    if not np.all(np.isfinite(vector)):
        raise ValueError('nonfinite_derived_input')
    return vector


def production_centers_scales():
    pb_center=math.log(PB_M)-BETA*math.log(ROE_M)+PB_OFFSET
    return np.array([PE_M,pb_center,GAP_M,DY_M]),np.array([PE_S,PB_SCALE,GAP_S,DY_S])


def z_from(raw,center,scale):
    z=(raw-center)/scale
    z[2]*=-1;z[3]*=-1
    return z


def curve(z):
    f=lambda x:100/(1+math.exp(K*x))
    lo,hi=f(ZC),f(-ZC)
    return max(0.0,min(100.0,(f(float(z))-lo)/(hi-lo)*100))


def overlay_damp(z):return 1.0 if z<=0 else max(0.0,min(1.0,1-z/ZC))


def allocation(z,earn_score,trend_risk_off):
    comp=float(np.dot(W,z));core=curve(comp)
    ea=max(-1.0,min(1.0,float(earn_score)))*EARN_MAX*overlay_damp(comp)
    ta=-TREND_PP if trend_risk_off else 0.0
    return {'composite_z':comp,'core_equity_pct':core,'earnings_adjustment_pp':ea,'trend_adjustment_pp':ta,'policy_equity_pct':max(0.0,min(100.0,core+ea+ta))}


def calibrate(x):
    # Even finite raw observations can overflow the squared deviations in std.
    # A nonfinite scale must never reach the strict JSON writer or publication.
    with np.errstate(over='ignore', invalid='ignore'):
        center=np.median(x,axis=0);scale=np.std(x,axis=0,ddof=0)
    if (not np.all(np.isfinite(center)) or not np.all(np.isfinite(scale))
            or np.any(scale<=1e-12)):
        raise RuntimeError('invalid_descriptive_scale')
    return center,scale


def js(a):return [float(x) for x in np.asarray(a)]


def main(output_path=None):
    out_path = Path(output_path) if output_path is not None else OUT
    out_path.unlink(missing_ok=True)  # stale evidence cannot pass the publication gate
    try:
        version=guard_model_source()
    except (OSError, UnicodeError, RuntimeError):
        # The source-constant guard is part of the entrypoint, not a preflight
        # that may leave no artifact after stale evidence was removed.
        write_withheld(out_path, 'model_source_validation_failed', 'unverified')
        return
    try:
        screen_bytes=SCREEN.read_bytes()
        screen=json.loads(screen_bytes)
        latest=json.loads(LATEST.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError):
        write_withheld(out_path, 'unavailable_or_invalid_calibration_input', version)
        return
    if (not isinstance(screen, dict)
            or not isinstance(screen.get('records'), list)
            or not all(isinstance(row, dict) for row in screen['records'])
            or not isinstance(latest, dict)
            or not isinstance(latest.get('nifty'), dict)
            or not isinstance(latest.get('earnings'), dict)
            or not isinstance(latest.get('trend'), dict)):
        write_withheld(out_path, 'invalid_calibration_input_structure', version)
        return
    try:
        reliability=json.loads(RELIABILITY.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError):
        write_withheld(out_path, 'unavailable_or_invalid_reliability_document', version)
        return
    if latest.get('model_version')!=version:
        write_withheld(out_path, 'latest_model_version_mismatch', version)
        return
    rows=[row for row in screen['records'] if row.get('methodology_era')=='Current ratio definitions']
    if len(rows)!=36:
        write_withheld(out_path, 'invalid_current_definition_count', version)
        return
    try:
        if any(not isinstance(row.get('signal_date'), str) or not row['signal_date'] for row in rows):
            raise ValueError('invalid_signal_date')
        x=np.vstack([raw_vector(row['pe'],row['pb'],row['dy'],row['gsec10']) for row in rows])
        n=latest['nifty']
        cur=raw_vector(n['pe'],n['pb'],n['div_yield'],n['gsec10'])
        if (not isinstance(n.get('date'), str) or not n['date']
                or not isinstance(n.get('gsec_meta'), dict)
                or not isinstance(n['gsec_meta'].get('asof'), str)
                or not n['gsec_meta']['asof']):
            raise ValueError('invalid_market_vintage')
        level=n['level']
        if (isinstance(level, bool) or not isinstance(level, (int, float))
                or not math.isfinite(level) or level <= 0):
            raise ValueError('invalid_market_level')
        earn=float(latest['earnings']['score'])
        if not math.isfinite(earn):
            raise ValueError('invalid_earnings_score')
        risk_off=latest['trend']['risk_off']
        if not isinstance(risk_off, bool):
            raise ValueError('invalid_trend_risk_off')
    except (KeyError, TypeError, ValueError, OverflowError):
        write_withheld(out_path, 'invalid_calibration_input_values', version)
        return
    # All derived calibration calculations must produce an explicit withheld
    # research artifact on numerical overflow, not an unrecorded exception.
    # Do not catch the hard RuntimeError from enforce_reproduction.
    try:
        pc,ps=production_centers_scales();prod_z=z_from(cur,pc,ps);prod=allocation(prod_z,earn,risk_off)
        expected, reason = validate_anchor(reliability)
        if reason:
            write_withheld(out_path, reason, version)
            return
        provenance_reason = validate_provenance(reliability, root=ROOT, latest=latest, model_version=version)
        if provenance_reason:
            write_withheld(out_path, provenance_reason, version)
            return
        enforce_reproduction(out_path, version, prod['policy_equity_pct'], expected)

        # Preflight every deterministic sensitivity window before constructing any
        # report. This includes the full 36, six leave-block-out 30, and two 18
        # month windows. All must have finite, nondegenerate descriptive scales.
        try:
            calibrate(x)
            for block in range(6):
                calibrate(x[[i for i in range(36) if i // 6 != block]])
            calibrate(x[:18])
            calibrate(x[18:])
        except (RuntimeError, ValueError, OverflowError, FloatingPointError):
            write_withheld(out_path, 'invalid_descriptive_scale', version)
            return

        variants=[]
        def add(name,idx,note):
            xx=x[np.asarray(idx,dtype=int)];c,s=calibrate(xx);z=z_from(cur,c,s);a=allocation(z,earn,risk_off)
            variants.append({'name':name,'n_months':len(xx),'note':note,'center':dict(zip(LABELS,js(c))),'scale':dict(zip(LABELS,js(s))),'current_z':dict(zip(LABELS,js(z))),**a})
        add('full_36_descriptive',range(36),'Descriptive recalibration on all 36 current-definition observations; not an OOS candidate.')
        for b in range(6):
            omit=set(range(b*6,(b+1)*6));keep=[i for i in range(36) if i not in omit]
            add(f'leave_months_{b*6+1:02d}_{(b+1)*6:02d}_out',keep,f'Omits contiguous current-definition observations {b*6+1}-{(b+1)*6}; 30 months remain.')
        add('first_18_only',range(18),'Early-half regime sensitivity only.')
        add('last_18_only',range(18,36),'Late-half regime sensitivity only.')

        loo=[v for v in variants if v['name'].startswith('leave_months_')]
        vals=[v['policy_equity_pct'] for v in loo]
        lens_impacts={k:[] for k in LABELS}
        for v in loo:
            alt=np.array([v['current_z'][k] for k in LABELS])
            for i,k in enumerate(LABELS):
                z=prod_z.copy();z[i]=alt[i];a=allocation(z,earn,risk_off)
                lens_impacts[k].append({'variant':v['name'],'policy_equity_pct':a['policy_equity_pct'],'change_vs_production_pp':a['policy_equity_pct']-prod['policy_equity_pct']})
        impact_summary={k:{'min_change_pp':min(q['change_vs_production_pp'] for q in arr),'max_change_pp':max(q['change_vs_production_pp'] for q in arr),'max_abs_change_pp':max(abs(q['change_vs_production_pp']) for q in arr)} for k,arr in lens_impacts.items()}
        fc,fs=calibrate(x)
        out={
          'calibration_screen_sha256': hashlib.sha256(screen_bytes).hexdigest(),
          'anchor_provenance': {'evaluated_at': reliability['evaluated_at'], 'source_hashes': reliability['source_hashes']},
          'schema_version':2,'publication_status':'published','withheld_reason':None,'anchor_status':'verified','generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'research_only':True,'model_version':version,
          'question':'How fragile is today’s policy allocation to deterministic re-estimation of lens centers/scales within the short current-definition era?',
          'sample':{'months':36,'first_signal_date':rows[0]['signal_date'],'last_signal_date':rows[-1]['signal_date'],'methodology':'Current ratio definitions','historical_yield_caveat':screen.get('yield_rule')},
          'current_packet':{'generated_at':latest['generated_at'],'nifty_date':n['date'],'level':n['level'],'pe':n['pe'],'pb':n['pb'],'dividend_yield':n['div_yield'],'gsec10':n['gsec10'],'gsec_asof':n['gsec_meta']['asof']},
          'production_reproduction':{'centers':dict(zip(LABELS,js(pc))),'scales':dict(zip(LABELS,js(ps))),'current_z':dict(zip(LABELS,js(prod_z))),**prod},
          'full_36_descriptive_recalibration':{'centers':dict(zip(LABELS,js(fc))),'scales':dict(zip(LABELS,js(fs)))},
          'leave_six_month_block_out':{'variants':6,'min_policy_equity_pct':min(vals),'max_policy_equity_pct':max(vals),'range_pp':max(vals)-min(vals),'min_change_vs_production_pp':min(vals)-prod['policy_equity_pct'],'max_change_vs_production_pp':max(vals)-prod['policy_equity_pct']},
          'one_lens_at_a_time_leave_block_sensitivity':impact_summary,
          'variants':variants,
          'interpretation_guardrail':'These deterministic recalibrations quantify assumption fragility only. They are not confidence intervals, intrinsic-value estimates, optimized parameters, or alternative live candidates. The historical yield series differs from the current daily RBI security-yield proxy, so gap sensitivity carries an additional definition mismatch.',
          'return_data_used':False,'live_model_changed':False,'live_allocation_changed':False
        }
        write_report(out_path, out)
    except (OverflowError, ValueError, FloatingPointError):
        write_withheld(out_path, 'invalid_calibration_numerics', version)
        return
    print(json.dumps({'production':out['production_reproduction'],'leave_six_month_block_out':out['leave_six_month_block_out'],'one_lens_at_a_time':impact_summary,'variant_targets':[{'name':v['name'],'equity':v['policy_equity_pct']} for v in variants]},indent=2))


def verify_recomputed_payload(report):
    """Reject edited/replayed sensitivity numbers, not merely stale input receipts.

    Recompute from the current provenance-bound inputs into a disposable file;
    compare every published field except the non-deterministic audit clock.
    This is a same-code consistency check, NOT independent PIT validation.
    """
    import tempfile
    with tempfile.TemporaryDirectory(prefix='calibration-verify-') as folder:
        recomputed_path = Path(folder) / 'recomputed.json'
        main(recomputed_path)
        recomputed = json.loads(recomputed_path.read_text(encoding='utf-8'))
    if recomputed.get('publication_status') != 'published':
        raise SystemExit('calibration_publication_blocked: recomputation_withheld')
    without_clock = lambda packet: {k: v for k, v in packet.items() if k != 'generated_at'}
    if without_clock(report) != without_clock(recomputed):
        raise SystemExit('calibration_publication_blocked: recalculated_payload_mismatch')


if __name__ == '__main__':
    if sys.argv[1:] == ['--verify-publication']:
        # Gate source receipts AND independently re-run deterministic descriptive
        # calculations before allowing the research artifact to be published.
        report = verify_publication(OUT, root=ROOT, latest=json.loads(LATEST.read_text()),
                                    reliability=json.loads(RELIABILITY.read_text()), model_version=guard_model_source(), screen=SCREEN)
        verify_recomputed_payload(report)
        # Recheck source identity after recomputation to narrow TOCTOU exposure.
        verify_publication(OUT, root=ROOT, latest=json.loads(LATEST.read_text()),
                           reliability=json.loads(RELIABILITY.read_text()), model_version=guard_model_source(), screen=SCREEN)
    elif len(sys.argv) == 1:
        main()
    else:
        raise SystemExit('usage: calibration_stability_audit.py [--verify-publication]')
