#!/usr/bin/env python3
"""Comprehensive evidence gate for Anup Nifty Valuation.

Research only. This evaluator is intentionally harder to pass than the model is
to run. It does not edit model.js, does not choose new parameters, and does not
promote a challenger.

It evaluates the valuation-core history currently reproducible in this project
and separately carries forward current-model sensitivity and crash-challenger
evidence. A missing point-in-time full-stack history is reported as NOT TESTABLE
rather than backfilled with invented release lags.
"""
from __future__ import annotations

from pathlib import Path
from statistics import NormalDist
from itertools import combinations
import hashlib
import json
import math

import numpy as np
import pandas as pd

import retrospective_core as r

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "robust_evaluation.json"
SEED = 20260913
BOOTSTRAP_DRAWS = 5000
BOOTSTRAP_BLOCKS = (3, 6, 12)
CSCV_SLICES = 8
LIVE_C10 = {
    "peM": 22.44,
    "peS": 2.08,
    "pbM": 3.54,
    "pbS": 0.3239941700435707,
    "roeM": 16.15402934929392,
    "roeS": 0.9884905234449538,
    "dyM": 1.25,
    "dyS": 0.18,
    "gapM": -2.60,
    "gapS": 0.70,
    "wPE": 30.0,
    "wPB": 25.0,
    "wGAP": 30.0,
    "wDY": 10.0,
    "beta": 0.60,
    "k": 1.35,
    "zc": 2.5,
    "macroMax": 6.0,
    "earnMax": 6.0,
}


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def sha256_file(path: Path):
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def panel_from_retrospective(data):
    if not data or data.get("status") != "complete":
        raise RuntimeError("data/retrospective.json is unavailable")
    p = pd.DataFrame(data["records"]).rename(columns={"dividend_yield": "dy"})
    p.index = pd.PeriodIndex(p.pop("month"), freq="M")
    r.validate_panel(p)
    return p


def cagr(rets):
    a = np.asarray(rets, float)
    if len(a) == 0:
        return None
    wealth = float(np.prod(1.0 + a))
    years = len(a) / 12.0
    if wealth <= 0 or years <= 0:
        return None
    return wealth ** (1.0 / years) - 1.0


def monthly_sharpe(rets):
    a = np.asarray(rets, float)
    if len(a) < 3:
        return None
    s = float(np.std(a, ddof=1))
    if s <= 1e-15:
        return None
    return float(np.mean(a) / s)


def t_stat(rets):
    a = np.asarray(rets, float)
    if len(a) < 3:
        return None
    s = float(np.std(a, ddof=1))
    if s <= 1e-15:
        return None
    return float(np.mean(a) / (s / math.sqrt(len(a))))


def net_with_weights(weights, eq, db, cost=r.COST_PER_100_TURNOVER):
    w = pd.Series(np.asarray(weights, float), index=eq.index, dtype=float)
    gross = w * eq + (1.0 - w) * db
    turn = r.rebalance_turnover(w, eq, db)
    net = (1.0 - float(cost) * turn) * (1.0 + gross) - 1.0
    return pd.Series(net, index=eq.index, dtype=float), np.asarray(turn, float)


def percentile(value, sample):
    a = np.asarray(sample, float)
    below = float(np.sum(a < value))
    equal = float(np.sum(np.isclose(a, value, rtol=0, atol=1e-14)))
    return 100.0 * (below + 0.5 * equal) / len(a) if len(a) else None


def acf(x, lag):
    a = np.asarray(x, float)
    if lag <= 0 or len(a) <= lag:
        return None
    x0, x1 = a[:-lag], a[lag:]
    if float(np.std(x0)) <= 1e-15 or float(np.std(x1)) <= 1e-15:
        return None
    return float(np.corrcoef(x0, x1)[0, 1])


def effective_sample_size(x, max_lag=12):
    a = np.asarray(x, float)
    n = len(a)
    if n < 3:
        return {"raw_n": n, "effective_n": n, "positive_acf_sum": 0.0}
    pos = []
    vals = {}
    for lag in range(1, min(max_lag, n - 1) + 1):
        rho = acf(a, lag)
        vals[str(lag)] = rho
        if rho is not None and rho > 0:
            pos.append(rho)
    design = 1.0 + 2.0 * sum(pos)
    neff = max(1.0, min(float(n), n / design))
    return {
        "raw_n": int(n),
        "effective_n": float(neff),
        "positive_acf_sum": float(sum(pos)),
        "acf_1_to_12": vals,
        "method": "Bartlett-style design effect using positive autocorrelations through 12 months; diagnostic, not a formal finite-sample correction",
    }


def moving_block_bootstrap(diff, block, draws=BOOTSTRAP_DRAWS, seed=SEED):
    a = np.asarray(diff, float)
    n = len(a)
    if n < block or block < 1:
        return None
    rng = np.random.default_rng(seed + int(block))
    out = np.empty(draws, dtype=float)
    blocks_needed = int(math.ceil(n / block))
    base = np.arange(n)
    for i in range(draws):
        starts = rng.integers(0, n, size=blocks_needed)
        idx = np.concatenate([(base[s:s + block] if s + block <= n else np.r_[base[s:], base[:(s + block) % n]]) for s in starts])[:n]
        out[i] = 1200.0 * float(np.mean(a[idx]))
    return {
        "block_months": int(block),
        "draws": int(draws),
        "annualized_mean_timing_pp": 1200.0 * float(np.mean(a)),
        "ci95_pp": [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))],
        "probability_mean_gt_zero": float(np.mean(out > 0)),
    }


def fair_null_placebo(panel):
    frame, _, dynamic_net, _ = r.strategy_returns(panel, r.LIVE_K, r.LIVE_ZC)
    eq, db = frame.eq.astype(float), frame.db.astype(float)
    w = frame.w.astype(float)
    mean_w = float(w.mean())
    static_w = pd.Series(mean_w, index=frame.index, dtype=float)
    static_net, static_turn = net_with_weights(static_w, eq, db)
    timing = dynamic_net - static_net
    dyn_cagr = float(cagr(dynamic_net))
    sta_cagr = float(cagr(static_net))
    actual_excess_pp = 100.0 * (dyn_cagr - sta_cagr)

    placebo = []
    wa = w.to_numpy(dtype=float)
    for shift in range(1, len(wa)):
        pnet, pturn = net_with_weights(np.roll(wa, shift), eq, db)
        placebo.append({
            "shift": int(shift),
            "excess_cagr_pp": 100.0 * float(cagr(pnet) - sta_cagr),
            "realised_turnover_x": float(pturn.sum()),
        })
    px = [x["excess_cagr_pp"] for x in placebo]
    boot = [moving_block_bootstrap(timing, b) for b in BOOTSTRAP_BLOCKS]
    return {
        "months": int(len(frame)),
        "mean_equity_pct": 100.0 * mean_w,
        "dynamic_net": r.stats(dynamic_net.to_numpy(), w.to_numpy(), True),
        "beta_matched_static_net": r.stats(static_net.to_numpy(), static_w.to_numpy(), True),
        "dynamic_minus_static_cagr_pp": actual_excess_pp,
        "net_timing_mean_annualized_pp": 1200.0 * float(timing.mean()),
        "net_timing_t_stat_naive": t_stat(timing),
        "timing_effective_sample": effective_sample_size(timing),
        "signal_weight_lag1_autocorrelation": acf(w, 1),
        "dynamic_realised_turnover_x": float(frame.turnover.sum()),
        "static_realised_turnover_x": float(static_turn.sum()),
        "placebo": {
            "method": "all non-zero circular shifts of the exact target-weight path against the unchanged return path",
            "unique_paths": int(len(placebo)),
            "actual_percentile": percentile(actual_excess_pp, px),
            "p05_excess_cagr_pp": float(np.percentile(px, 5)),
            "median_excess_cagr_pp": float(np.percentile(px, 50)),
            "p95_excess_cagr_pp": float(np.percentile(px, 95)),
            "max_excess_cagr_pp": float(np.max(px)),
        },
        "paired_moving_block_bootstrap": boot,
    }


def variant_matrix(panel):
    series = {}
    for zc in r.EXTREMES:
        for k in r.CURVES:
            key = r.grid_key(k, zc)
            frame, _, net, _ = r.strategy_returns(panel, k, zc)
            series[key] = pd.Series(net, index=frame.index, dtype=float)
    m = pd.DataFrame(series).dropna()
    if len(m) < 24 or m.shape[1] < 2:
        raise RuntimeError("Insufficient common variant matrix")
    return m


def deflated_sharpe_probability(rets, benchmark_sr):
    a = np.asarray(rets, float)
    sr = monthly_sharpe(a)
    if sr is None or len(a) < 4:
        return None
    s = pd.Series(a)
    skew = float(s.skew())
    kurt = float(s.kurt()) + 3.0
    den2 = 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr * sr
    if den2 <= 0:
        return None
    z = (sr - benchmark_sr) * math.sqrt(len(a) - 1.0) / math.sqrt(den2)
    return {
        "monthly_sharpe": float(sr),
        "benchmark_expected_max_monthly_sharpe": float(benchmark_sr),
        "probability": float(NormalDist().cdf(z)),
        "z": float(z),
        "skew": skew,
        "raw_kurtosis": kurt,
    }


def multiple_testing(panel):
    m = variant_matrix(panel)
    sharpes = {k: monthly_sharpe(m[k]) for k in m.columns}
    sr_values = np.asarray([v for v in sharpes.values() if v is not None], float)
    n_trials = len(sr_values)
    sr_std = float(np.std(sr_values, ddof=1)) if n_trials > 1 else 0.0
    nd = NormalDist()
    euler_gamma = 0.5772156649015329
    if n_trials > 1 and sr_std > 0:
        expected_max = sr_std * (
            (1.0 - euler_gamma) * nd.inv_cdf(1.0 - 1.0 / n_trials)
            + euler_gamma * nd.inv_cdf(1.0 - 1.0 / (n_trials * math.e))
        )
    else:
        expected_max = 0.0
    live_key = r.grid_key(r.LIVE_K, r.LIVE_ZC)
    best_key = max(sharpes, key=lambda k: sharpes[k] if sharpes[k] is not None else -1e99)

    # CSCV PBO: contiguous equal-ish slices; choose half as in-sample and rank
    # the selected in-sample winner in the complementary out-of-sample set.
    arr = m.to_numpy(dtype=float)
    t, n = arr.shape
    slices = np.array_split(np.arange(t), CSCV_SLICES)
    logits = []
    selected = {}
    for ins in combinations(range(CSCV_SLICES), CSCV_SLICES // 2):
        ins = set(ins)
        tr = np.concatenate([slices[i] for i in range(CSCV_SLICES) if i in ins])
        te = np.concatenate([slices[i] for i in range(CSCV_SLICES) if i not in ins])
        tr_sr = np.array([monthly_sharpe(arr[tr, j]) for j in range(n)], dtype=float)
        te_sr = np.array([monthly_sharpe(arr[te, j]) for j in range(n)], dtype=float)
        winner = int(np.nanargmax(tr_sr))
        selected[m.columns[winner]] = selected.get(m.columns[winner], 0) + 1
        target = te_sr[winner]
        less = float(np.sum(te_sr < target))
        equal = float(np.sum(np.isclose(te_sr, target, rtol=0, atol=1e-14)))
        rank = 1.0 + less + 0.5 * max(0.0, equal - 1.0)
        omega = rank / (n + 1.0)
        omega = min(max(omega, 1e-12), 1.0 - 1e-12)
        logits.append(math.log(omega / (1.0 - omega)))
    pbo = float(np.mean(np.asarray(logits) <= 0.0))

    return {
        "candidate_family": "valuation curve grid only",
        "trial_count": int(n_trials),
        "variant_months": int(len(m)),
        "monthly_sharpe_std_across_trials": sr_std,
        "expected_max_monthly_sharpe_under_selection": float(expected_max),
        "live_variant": {"key": live_key, **(deflated_sharpe_probability(m[live_key], expected_max) or {})},
        "best_observed_variant": {"key": best_key, **(deflated_sharpe_probability(m[best_key], expected_max) or {})},
        "cscv": {
            "slices": CSCV_SLICES,
            "splits": int(len(logits)),
            "pbo": pbo,
            "median_oos_rank_logit": float(np.median(logits)),
            "in_sample_winner_counts": selected,
        },
        "warning": "DSR/PBO adjust only this exact common 24-member valuation-curve family. Other research families have different samples/objectives and are logged separately rather than pooled mechanically.",
    }


def lens_redundancy(panel):
    c = r.C
    rows = []
    for _, x in panel.iterrows():
        pe, pb, dy, g = map(float, (x.pe, x.pb, x.dy, x.gsec10))
        roe = 100.0 * pb / pe
        gap = 100.0 / pe - g
        rows.append([
            (pe - c["peM"]) / c["peS"],
            (pb - c["pbM"]) / c["pbS"] - c["beta"] * (roe - c["roeM"]) / c["roeS"],
            -(gap - c["gapM"]) / c["gapS"],
            -(dy - c["dyM"]) / c["dyS"],
        ])
    names = ["pe", "pb_profitability_adjusted", "earnings_yield_minus_gsec", "dividend_yield"]
    df = pd.DataFrame(rows, index=panel.index, columns=names)
    corr = df.corr().to_numpy(dtype=float)
    eig = np.clip(np.linalg.eigvalsh(corr), 0.0, None)
    eff = float((eig.sum() ** 2) / np.square(eig).sum()) if np.square(eig).sum() > 0 else None
    off = corr.copy()
    np.fill_diagonal(off, np.nan)
    return {
        "months": int(len(df)),
        "correlation_matrix": {names[i]: {names[j]: float(corr[i, j]) for j in range(len(names))} for i in range(len(names))},
        "eigenvalues": [float(x) for x in eig],
        "effective_independent_lenses": eff,
        "max_absolute_pairwise_correlation": float(np.nanmax(np.abs(off))),
        "interpretation": "Four displayed valuation lenses are not four independent bets. Effective-lens count is the participation ratio of the correlation eigenvalues.",
    }


def curve10(z, k=LIVE_C10["k"], zc=LIVE_C10["zc"]):
    f = lambda x: 100.0 / (1.0 + math.exp(float(k) * float(x)))
    lo, hi = f(zc), f(-zc)
    return max(0.0, min(100.0, (f(z) - lo) / (hi - lo) * 100.0))


def fair_pe_fan(latest):
    if not latest or latest.get("model_version") != "3.10-pb-regime-1":
        return {"status": "unavailable", "reason": "current packet/model version does not match frozen V3.10 constants in this research audit"}
    n = latest.get("nifty", {})
    en = latest.get("earnings", {})
    mac = latest.get("macro", {})
    required = [n.get("pe"), n.get("pb"), n.get("div_yield"), n.get("gsec10"), en.get("score"), mac.get("score")]
    if not all(isinstance(x, (int, float)) and math.isfinite(float(x)) for x in required):
        return {"status": "unavailable", "reason": "latest packet lacks numeric sensitivity inputs"}
    pe, pb, dy, g = map(float, required[:4])
    roe, gap = 100.0 * pb / pe, 100.0 / pe - g
    rows = []
    for pe_ref in range(18, 27):
        z_pe = (pe - pe_ref) / LIVE_C10["peS"]
        z_pb = (pb - LIVE_C10["pbM"]) / LIVE_C10["pbS"] - LIVE_C10["beta"] * (roe - LIVE_C10["roeM"]) / LIVE_C10["roeS"]
        z_gap = -(gap - LIVE_C10["gapM"]) / LIVE_C10["gapS"]
        z_dy = -(dy - LIVE_C10["dyM"]) / LIVE_C10["dyS"]
        total_w = LIVE_C10["wPE"] + LIVE_C10["wPB"] + LIVE_C10["wGAP"] + LIVE_C10["wDY"]
        z = (LIVE_C10["wPE"] * z_pe + LIVE_C10["wPB"] * z_pb + LIVE_C10["wGAP"] * z_gap + LIVE_C10["wDY"] * z_dy) / total_w
        core = curve10(z)
        damp = max(0.0, min(1.0, 1.0 - abs(z) / LIVE_C10["zc"]))
        ea = max(-1.0, min(1.0, float(en["score"]))) * LIVE_C10["earnMax"] * damp
        ma = max(-1.0, min(1.0, float(mac["score"]))) * LIVE_C10["macroMax"] * damp
        final = max(0.0, min(100.0, core + ea + ma))
        rows.append({"assumed_fair_pe": pe_ref, "valuation_z": float(z), "core_equity_pct": float(core), "mechanical_full_equity_pct": float(final)})
    vals = [x["mechanical_full_equity_pct"] for x in rows]
    return {
        "status": "complete",
        "current_nifty_pe": pe,
        "fan": rows,
        "equity_range_pct": [float(min(vals)), float(max(vals))],
        "spread_pp": float(max(vals) - min(vals)),
        "note": "One-at-a-time reference sensitivity: only the assumed fair P/E anchor changes from 18 to 26; all other V3.10 inputs/references are held fixed. This is a dominance diagnostic, not a forecast.",
    }


def calibration_sensitivity(data):
    if not data or data.get("status") != "complete":
        return {"status": "unavailable"}
    cw = data.get("common_window", {})
    keys = ["fixed_reference_live_curve", "fixed_reference_yield_lag_2m", "rolling_36m_equal_lenses", "expanding_equal_lenses"]
    rows = {}
    for k in keys:
        q = cw.get(k)
        if q:
            rows[k] = {x: q.get(x) for x in ("months", "cagr_pct", "max_drawdown_pct", "annual_vol_pct", "annual_turnover_x", "first_signal", "last_signal")}
    return {
        "status": "complete" if rows else "unavailable",
        "common_window_methods": rows,
        "warning": "Rolling/expanding rules use prior observations but were designed retrospectively. Their existence exposes calibration sensitivity; it does not create untouched out-of-sample evidence.",
    }


def crash_challenger(trend):
    if not trend or trend.get("conclusion") is None:
        return {"status": "unavailable"}
    ref = trend.get("reference_variant", {})
    gate = trend.get("frozen_gate_assessment", {})
    return {
        "status": "complete",
        "policy_id": trend.get("policy_id"),
        "conclusion": trend.get("conclusion"),
        "max_drawdown_improvement_pp": ref.get("delta", {}).get("max_drawdown_improvement_pp"),
        "cagr_delta_pp": ref.get("delta", {}).get("cagr_delta_pp"),
        "covid_drawdown_improvement_pp": trend.get("stress_reference", {}).get("covid", {}).get("improvement_pp"),
        "historical_gate_drawdown_requirement_met": gate.get("drawdown_requirement_met"),
        "historical_result_can_promote_live": gate.get("historical_result_can_promote_live"),
        "note": "Trend is evaluated as a separate price-regime challenger; it is not allowed to retroactively rescue weak valuation timing statistics.",
    }


def track_record_heuristic(weight_rho1, delta_sharpe=0.20):
    rho = float(weight_rho1) if weight_rho1 is not None and math.isfinite(float(weight_rho1)) else 0.0
    design = (1.0 + max(0.0, rho)) / max(1e-9, 1.0 - max(0.0, rho))
    n95 = (1.959963984540054 / delta_sharpe) ** 2
    n80 = ((1.959963984540054 + 0.8416212335729143) / delta_sharpe) ** 2
    return {
        "target_sharpe_difference": delta_sharpe,
        "independent_observations_for_95pct_signal_to_noise": float(n95),
        "independent_observations_for_95pct_two_sided_80pct_power": float(n80),
        "observed_weight_lag1_rho": rho,
        "ar1_design_effect": float(design),
        "approx_calendar_months_95pct": int(math.ceil(n95 * design)),
        "approx_calendar_years_95pct": float(n95 * design / 12.0),
        "approx_calendar_months_80pct_power": int(math.ceil(n80 * design)),
        "approx_calendar_years_80pct_power": float(n80 * design / 12.0),
        "warning": "Heuristic only. It illustrates how persistent monthly signals can require decades of calendar history; it is not a substitute for a full power analysis under the true return process.",
    }


def prospective_month_count():
    p = ROOT / "data" / "evidence" / "decisions"
    if not p.exists():
        return 0
    return len(list(p.glob("*.json")))


def build():
    retro = load_json(ROOT / "data" / "retrospective.json")
    panel = panel_from_retrospective(retro)
    fair = fair_null_placebo(panel)
    multi = multiple_testing(panel)
    lens = lens_redundancy(panel)
    latest = load_json(ROOT / "data" / "latest.json")
    robust = load_json(ROOT / "data" / "robustness.json")
    trend = load_json(ROOT / "data" / "trend_challenger_summary.json")
    registry = load_json(ROOT / "research_trial_registry.json", {})
    policy = load_json(ROOT / "robust_evaluation_policy.json", {})
    prospective = prospective_month_count()

    bootstrap_pass = all(x is not None and x["ci95_pp"][0] > 0 for x in fair["paired_moving_block_bootstrap"])
    placebo_pass = fair["placebo"]["actual_percentile"] >= policy.get("promotion_evidence_thresholds", {}).get("placebo_percentile_min", 95)
    dsr_prob = multi.get("live_variant", {}).get("probability")
    dsr_pass = dsr_prob is not None and dsr_prob >= policy.get("promotion_evidence_thresholds", {}).get("deflated_sharpe_probability_min", 0.95)
    pbo = multi.get("cscv", {}).get("pbo")
    pbo_pass = pbo is not None and pbo <= policy.get("promotion_evidence_thresholds", {}).get("pbo_max", 0.10)
    prospective_pass = prospective >= policy.get("promotion_evidence_thresholds", {}).get("prospective_completed_months_min", 60)

    gates = {
        "exposure_matched_timing_edge_positive": fair["dynamic_minus_static_cagr_pp"] > 0,
        "placebo_95th_percentile": placebo_pass,
        "paired_block_bootstrap_all_lower_bounds_above_zero": bootstrap_pass,
        "deflated_sharpe_probability": dsr_pass,
        "cscv_pbo": pbo_pass,
        "prospective_months": prospective_pass,
        "certified_point_in_time_full_stack_history": False,
        "taxable_after_tax_implementation_test": False,
    }
    all_critical = all(gates.values())

    return {
        "schema_version": 1,
        "status": "complete",
        "scope": "Robust evaluation of the reproducible valuation core plus separately governed current-model sensitivities/challengers. It is not a certified historical backtest of the full V3.10 macro plus earnings stack.",
        "decision": "ELIGIBLE_FOR_SEPARATE_PROMOTION_REVIEW" if all_critical else "NOT_ELIGIBLE_FOR_PROMOTION",
        "decision_reason": "Every critical evidence gate must pass; no composite score can average away a failed gate.",
        "fair_null_and_timing": fair,
        "multiple_testing_and_overfit": multi,
        "sample_size": track_record_heuristic(fair["signal_weight_lag1_autocorrelation"]),
        "lens_redundancy": lens,
        "fair_pe_reference_sensitivity": fair_pe_fan(latest),
        "calibration_sensitivity": calibration_sensitivity(robust),
        "crash_challenger": crash_challenger(trend),
        "prospective_evidence": {
            "completed_decision_files": int(prospective),
            "minimum_required_before_any_promotion_review": int(policy.get("promotion_evidence_thresholds", {}).get("prospective_completed_months_min", 60)),
        },
        "implementation_status": {
            "transaction_costs": "10 bp one-way in the valuation-core timing audit; additional cost sensitivities exist elsewhere",
            "taxes": "NOT TESTED in this evaluator; therefore no taxable-investor net-return claim is allowed",
            "full_stack_release_vintages": "NOT TESTABLE until per-observation available_at history is reconstructed under release_timing_policy.json",
        },
        "trial_registry": registry,
        "gate_matrix": gates,
        "reproducibility": {
            "hash_algorithm": "sha256",
            "files": {str(p.relative_to(ROOT)): sha256_file(p) for p in [
                ROOT / "model.js",
                ROOT / "data" / "retrospective.json",
                ROOT / "data" / "latest.json",
                ROOT / "validation_policy.json",
                ROOT / "robust_evaluation_policy.json",
                ROOT / "research_trial_registry.json",
                ROOT / "release_timing_policy.json",
            ]},
        },
        "governance": "No output from this evaluator changes live parameters automatically. Failed or unavailable gates remain visible and cannot be neutral-filled.",
    }


def main():
    try:
        out = build()
    except Exception as exc:
        out = {
            "schema_version": 1,
            "status": "unavailable",
            "decision": "NOT_ELIGIBLE_FOR_PROMOTION",
            "error": f"{type(exc).__name__}: {exc}",
            "governance": "Evaluation failure cannot promote or alter the live model.",
        }
    OUT.write_text(json.dumps(out, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({
        "status": out.get("status"),
        "decision": out.get("decision"),
        "months": out.get("fair_null_and_timing", {}).get("months"),
        "placebo_percentile": out.get("fair_null_and_timing", {}).get("placebo", {}).get("actual_percentile"),
        "dsr_probability": out.get("multiple_testing_and_overfit", {}).get("live_variant", {}).get("probability"),
        "pbo": out.get("multiple_testing_and_overfit", {}).get("cscv", {}).get("pbo"),
        "error": out.get("error"),
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
