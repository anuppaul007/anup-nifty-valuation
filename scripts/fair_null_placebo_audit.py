#!/usr/bin/env python3
"""Fair-null and placebo audit for the valuation-core timing rule.

Research only. This script does not alter the live allocator.

It addresses two specific evidence questions:
1) Does the dynamic rule add value versus a static portfolio with the same
   realised mean equity weight?
2) Is the timing alignment better than circularly shifted placebo weight paths
   that preserve the weight path's mean, circular turnover and circular
   autocorrelation exactly?

The input is data/retrospective.json, so the historical limitations documented
there still apply. In particular, this is valuation-core evidence only and is
not a point-in-time full macro/earnings backtest.
"""
from __future__ import annotations

from pathlib import Path
import json
import math

import numpy as np
import pandas as pd

import retrospective_core as r

ROOT = Path(__file__).resolve().parents[1]
INFILE = ROOT / "data" / "retrospective.json"
OUTFILE = ROOT / "data" / "fair_null_placebo_audit.json"
SEED = 20260913
MONTE_CARLO_DRAWS = 1000


def _panel_from_records(data):
    p = pd.DataFrame(data["records"]).rename(columns={"dividend_yield": "dy"})
    p.index = pd.PeriodIndex(p.pop("month"), freq="M")
    r.validate_panel(p)
    return p


def _aligned_frame(panel):
    z = panel.apply(r.valuation_z, axis=1)
    w = z.map(lambda x: r.curve(float(x)) / 100.0)
    eq = panel.equity_tri.pct_change().shift(-1)
    db = panel.debt_tri.pct_change().shift(-1)
    f = pd.DataFrame({"w": w, "eq": eq, "db": db}).dropna()
    if len(f) < 24:
        raise RuntimeError(f"Only {len(f)} aligned return months")
    return f


def _net_returns(weights, eq, db, cost=r.COST_PER_100_TURNOVER):
    weights = pd.Series(np.asarray(weights, float), index=eq.index, dtype=float)
    gross = weights * eq + (1.0 - weights) * db
    turn = r.rebalance_turnover(weights, eq, db)
    net = (1.0 - float(cost) * turn) * (1.0 + gross) - 1.0
    return pd.Series(gross, index=eq.index), pd.Series(net, index=eq.index), np.asarray(turn, float)


def _cagr(returns):
    a = np.asarray(returns, float)
    if not len(a):
        return None
    wealth = float(np.prod(1.0 + a))
    years = len(a) / 12.0
    return wealth ** (1.0 / years) - 1.0 if wealth > 0 and years > 0 else None


def _t_stat(x):
    a = np.asarray(x, float)
    if len(a) < 3:
        return None
    s = float(np.std(a, ddof=1))
    if s <= 0:
        return None
    return float(np.mean(a) / (s / math.sqrt(len(a))))


def _circular_lag1(x):
    a = np.asarray(x, float)
    if len(a) < 3 or float(np.std(a)) <= 0:
        return None
    b = np.roll(a, 1)
    return float(np.corrcoef(a, b)[0, 1])


def _circular_turnover(x):
    a = np.asarray(x, float)
    if not len(a):
        return 0.0
    return float(np.abs(a - np.roll(a, 1)).sum())


def _percentile(value, sample):
    a = np.asarray(sample, float)
    if not len(a):
        return None
    # Mid-rank percentile is stable when duplicate placebo values occur.
    below = float(np.sum(a < value))
    equal = float(np.sum(np.isclose(a, value, rtol=0, atol=1e-14)))
    return 100.0 * (below + 0.5 * equal) / len(a)


def build(data):
    if data.get("status") != "complete":
        raise RuntimeError("retrospective.json is unavailable")

    panel = _panel_from_records(data)
    f = _aligned_frame(panel)
    eq, db = f["eq"].astype(float), f["db"].astype(float)
    dynamic_w = f["w"].astype(float)

    dyn_gross, dyn_net, dyn_turn = _net_returns(dynamic_w, eq, db)
    mean_w = float(dynamic_w.mean())
    static_w = pd.Series(mean_w, index=f.index, dtype=float)
    static_gross, static_net, static_turn = _net_returns(static_w, eq, db)

    # Brinson-style allocation/timing effect relative to the beta-matched null.
    # Gross identity: dynamic gross = static gross + allocation effect.
    allocation_effect = (dynamic_w - mean_w) * (eq - db)
    gross_identity_error = float(np.max(np.abs((dyn_gross - static_gross) - allocation_effect)))
    net_timing = dyn_net - static_net
    differential_cost_effect = net_timing - allocation_effect

    actual_excess_cagr = float(_cagr(dyn_net) - _cagr(static_net))
    actual_timing_mean = float(net_timing.mean())

    w = dynamic_w.to_numpy(dtype=float)
    n = len(w)
    if n < 3:
        raise RuntimeError("Need at least three aligned months for placebo audit")

    # Circular shifts are the clean placebo for this question: every shifted
    # path uses exactly the same weights in a different phase relative to
    # returns. Therefore mean, distribution, circular turnover and circular
    # autocorrelation are preserved exactly. Realised trading turnover after
    # market drift is allowed to differ because that is part of path alignment.
    unique = []
    for shift in range(1, n):
        pw = np.roll(w, shift)
        _, pnet, pturn = _net_returns(pw, eq, db)
        unique.append({
            "shift": int(shift),
            "excess_cagr_pp": 100.0 * float(_cagr(pnet) - _cagr(static_net)),
            "timing_mean_annualized_pp": 1200.0 * float((pnet - static_net).mean()),
            "timing_t_stat": _t_stat(pnet - static_net),
            "realised_turnover_x": float(pturn.sum()),
        })

    unique_excess = [x["excess_cagr_pp"] for x in unique]
    exact_percentile = _percentile(100.0 * actual_excess_cagr, unique_excess)

    rng = np.random.default_rng(SEED)
    offsets = rng.integers(1, n, size=MONTE_CARLO_DRAWS)
    lookup = {x["shift"]: x for x in unique}
    mc = [lookup[int(k)]["excess_cagr_pp"] for k in offsets]

    invariants = {
        "mean_equity_dynamic_pct": 100.0 * mean_w,
        "mean_equity_placebo_max_abs_error_pp": 100.0 * max(abs(float(np.mean(np.roll(w, s))) - mean_w) for s in range(1, n)),
        "circular_turnover_dynamic_x": _circular_turnover(w),
        "circular_turnover_placebo_max_abs_error_x": max(abs(_circular_turnover(np.roll(w, s)) - _circular_turnover(w)) for s in range(1, n)),
        "circular_lag1_dynamic": _circular_lag1(w),
        "circular_lag1_placebo_max_abs_error": max(abs(_circular_lag1(np.roll(w, s)) - _circular_lag1(w)) for s in range(1, n)),
    }

    return {
        "schema_version": 1,
        "status": "complete",
        "research_scope": "valuation core only; no live parameter change",
        "source": "data/retrospective.json",
        "period": {"first_return_month": str(f.index.min()), "last_return_month": str(f.index.max()), "months": int(n)},
        "fair_null": {
            "definition": "constant equity target equal to the dynamic rule's realised mean target weight, with the same drift-aware monthly rebalance and 10 bp one-way turnover-cost convention",
            "static_equity_pct": 100.0 * mean_w,
            "dynamic_net": r.stats(dyn_net.to_numpy(), dynamic_w.to_numpy(), True),
            "beta_matched_static_net": r.stats(static_net.to_numpy(), static_w.to_numpy(), True),
            "dynamic_minus_static_cagr_pp": 100.0 * actual_excess_cagr,
            "dynamic_realised_turnover_x": float(dyn_turn.sum()),
            "static_realised_turnover_x": float(static_turn.sum()),
        },
        "brinson_style_timing": {
            "gross_identity": "(w_t - w_bar) * (R_equity_t - R_debt_t)",
            "gross_identity_max_abs_error": gross_identity_error,
            "allocation_effect_mean_annualized_pp": 1200.0 * float(allocation_effect.mean()),
            "differential_cost_effect_mean_annualized_pp": 1200.0 * float(differential_cost_effect.mean()),
            "net_timing_mean_annualized_pp": 1200.0 * actual_timing_mean,
            "net_timing_t_stat": _t_stat(net_timing),
            "note": "The t-stat is descriptive only; monthly observations are serially dependent and the effective sample is smaller than the raw month count.",
        },
        "placebo": {
            "method": "circularly shift the actual weight path against the fixed return path",
            "why": "preserves the weight path's mean, empirical distribution, circular turnover and circular lag-1 autocorrelation exactly while destroying its calendar alignment with returns",
            "unique_nonzero_shifts": int(n - 1),
            "monte_carlo_draws": MONTE_CARLO_DRAWS,
            "seed": SEED,
            "actual_excess_cagr_pp": 100.0 * actual_excess_cagr,
            "actual_percentile_vs_all_unique_shifts": exact_percentile,
            "actual_percentile_vs_1000_draws": _percentile(100.0 * actual_excess_cagr, mc),
            "placebo_excess_cagr_pp": {
                "p05": float(np.percentile(unique_excess, 5)),
                "median": float(np.percentile(unique_excess, 50)),
                "p95": float(np.percentile(unique_excess, 95)),
                "max": float(np.max(unique_excess)),
            },
            "invariants": invariants,
            "unique_results": unique,
        },
        "governance": "Evidence only. A favorable percentile or t-stat is not an automatic promotion trigger and does not repair current-vintage or methodology-break limitations.",
    }


def main():
    try:
        data = json.loads(INFILE.read_text(encoding="utf-8"))
        out = build(data)
    except Exception as exc:
        out = {"schema_version": 1, "status": "unavailable", "error": f"{type(exc).__name__}: {exc}", "governance": "No live parameter change."}
    OUTFILE.write_text(json.dumps(out, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({
        "status": out.get("status"),
        "months": out.get("period", {}).get("months"),
        "static_equity_pct": out.get("fair_null", {}).get("static_equity_pct"),
        "timing_t_stat": out.get("brinson_style_timing", {}).get("net_timing_t_stat"),
        "placebo_percentile": out.get("placebo", {}).get("actual_percentile_vs_all_unique_shifts"),
        "error": out.get("error"),
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
