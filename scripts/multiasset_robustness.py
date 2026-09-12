#!/usr/bin/env python3
"""Multi-asset robustness audit V2.

This script does NOT alter the live V3.6 NIFTY signal or research-v1 metal/BTC
allocation. It stress-tests whether the extra complexity adds value versus
simpler alternatives and whether conclusions survive reasonable assumptions.

Audits
------
1. Dynamic Gold/Silver versus static metal allocations on the same eligible era.
2. Proportional versus equity-first versus debt-first metal funding.
3. Gold/Silver-ratio lookbacks: 3y, 5y, 7y, 10y, expanding, plus robust median/MAD.
4. Gold and Silver one-factor-at-a-time ablations.
5. Deterministic parameter perturbation around the published research-v1 choices.
6. BTC-only-era diagnostics so pre-BTC crises cannot dominate its risk statistics.

The output is research evidence only. No live parameter is changed automatically.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import json
import math
import random

import numpy as np
import pandas as pd

import multiasset_backtest as mb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "multiasset_robustness.json"
SEED = 20260912
PERTURBATIONS = 500

GOLD_WEIGHTS = {
    "real_yield": 0.35,
    "broad_usd_3m": 0.25,
    "gold_12m_momentum": 0.25,
    "vix_stress": 0.15,
}
SILVER_WEIGHTS = {
    "gold_silver_ratio": 0.45,
    "china_industrial": 0.30,
    "silver_12m_momentum": 0.25,
}


def finite(x):
    return mb.finite(x)


def clip(x, a, b):
    return mb.clip(x, a, b)


def normalized(weights, drop=None):
    q = {k: float(v) for k, v in weights.items() if k != drop and float(v) > 0}
    total = sum(q.values())
    if total <= 0:
        raise ValueError("No active weights")
    return {k: v / total for k, v in q.items()}


def weighted_score(components, weights, drop=None):
    w = normalized(weights, drop)
    if any(k not in components or not finite(components[k]) for k in w):
        return None
    return sum(float(components[k]) * v for k, v in w.items())


def gold_components(gold_usd, mac, dt):
    real, _ = mb.last_on_or_before(mac["real"], dt, 10)
    vix, _ = mb.last_on_or_before(mac["vix"], dt, 10)
    mo = pd.Period(pd.Timestamp(dt), freq="M") - 1
    if mo not in mac["usd3"].index:
        return None
    usd3 = float(mac["usd3"].loc[mo])
    mom = mb.pct_near_year(gold_usd, dt)
    if not all(finite(x) for x in (real, vix, usd3, mom)):
        return None
    return {
        "real_yield": mb.squash(-(real - 1.5), 1.25),
        "broad_usd_3m": mb.squash(-usd3, 4.0),
        "gold_12m_momentum": mb.squash(mom, 20.0),
        "vix_stress": mb.squash(vix - 20, 10.0),
    }


def _ratio_z(current, history, robust=False):
    h = pd.Series(history, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if len(h) < 2:
        return None
    if robust:
        center = float(h.median())
        mad = float((h - center).abs().median())
        scale = 1.4826 * mad
    else:
        center = float(h.mean())
        scale = float(h.std(ddof=0))
    if not finite(scale) or scale < 1e-9:
        return None
    return clip((float(current) - center) / scale, -3, 3)


def silver_components(
    gold_usd,
    silver_usd,
    mac,
    dt,
    ratio_obs=756,
    min_obs=250,
    robust_ratio=False,
):
    dt = pd.Timestamp(dt)
    g = gold_usd[gold_usd.index <= dt]
    s = silver_usd[silver_usd.index <= dt]
    x = pd.concat([g.rename("g"), s.rename("s")], axis=1).dropna()
    x = x[(x.g > 0) & (x.s > 0)]
    feat = mb.rolling_price_features(silver_usd, dt)
    pmi_m = pd.Period(dt, freq="M") - 1
    if feat is None or pmi_m not in mac["china"].index or len(x) < 260:
        return None
    ratio = x.g / x.s
    hist = ratio.iloc[:-1]
    if ratio_obs is not None:
        hist = hist.tail(int(ratio_obs))
    if len(hist) < int(min_obs):
        return None
    z = _ratio_z(float(ratio.iloc[-1]), hist, robust_ratio)
    if not finite(z):
        return None
    pmi = float(mac["china"].loc[pmi_m])
    return {
        "gold_silver_ratio": mb.squash(z, 1.5),
        "china_industrial": mb.squash((pmi - 50) / 1.75, 1.5),
        "silver_12m_momentum": mb.squash(feat["momentum_12m_pct"], 30.0),
    }


def target_from_components(
    gold_c,
    silver_c,
    gold_drop=None,
    silver_drop=None,
    gold_weights=None,
    silver_weights=None,
    gold_center=13.0,
    gold_slope=5.0,
    silver_center=3.5,
    silver_slope=3.5,
):
    if gold_c is None or silver_c is None:
        return None
    gs = weighted_score(gold_c, gold_weights or GOLD_WEIGHTS, gold_drop)
    ss = weighted_score(silver_c, silver_weights or SILVER_WEIGHTS, silver_drop)
    if not finite(gs) or not finite(ss):
        return None
    g = clip(gold_center + gold_slope * gs, 8, 18) / 100.0
    s = clip(silver_center + silver_slope * ss, 0, 7) / 100.0
    return g, s, float(gs), float(ss)


def fund_metals(eq, debt, gold, silver, mode="proportional"):
    eq, debt, gold, silver = map(float, (eq, debt, gold, silver))
    metals = gold + silver
    if min(eq, debt, gold, silver) < -1e-12 or abs(eq + debt - 1) > 1e-8:
        raise ValueError("Invalid starting allocation")
    if metals > 1 + 1e-12:
        raise ValueError("Metal allocation above 100%")
    if mode == "proportional":
        retained = 1 - metals
        we, wd = eq * retained, debt * retained
    elif mode == "equity_first":
        from_eq = min(eq, metals)
        we = eq - from_eq
        wd = debt - (metals - from_eq)
    elif mode == "debt_first":
        from_debt = min(debt, metals)
        wd = debt - from_debt
        we = eq - (metals - from_debt)
    else:
        raise ValueError(f"Unknown funding mode: {mode}")
    if we < -1e-10 or wd < -1e-10:
        raise ValueError(f"Funding mode produced negative sleeve: {mode}")
    out = {"equity": max(0.0, we), "debt": max(0.0, wd), "gold": gold, "silver": silver}
    if abs(sum(out.values()) - 1) > 1e-8:
        raise ValueError("Funded allocation does not sum to 100%")
    return out


def net_return_series(months, rets, weights, cost_bps=10):
    prev = None
    out = []
    for mo, r, w in zip(months, rets, weights):
        if not finite(r):
            continue
        turn = 0.0 if prev is None else 0.5 * sum(
            abs(float(w.get(k, 0)) - float(prev.get(k, 0))) for k in set(w) | set(prev)
        )
        rn = float(r) - turn * (float(cost_bps) / 10000.0)
        out.append((mo, rn))
        prev = w
    return out


def enhanced_metrics(months, rets, weights, cost_bps=10):
    base = mb.metrics(months, rets, weights, cost_bps)
    if base is None:
        return None
    nr = net_return_series(months, rets, weights, cost_bps)
    rs = np.array([r for _, r in nr], dtype=float)
    downside = rs[rs < 0]
    downside_sd = float(downside.std(ddof=1)) if len(downside) > 1 else None
    sortino = (
        float(rs.mean() / downside_sd * math.sqrt(12))
        if finite(downside_sd) and downside_sd > 1e-12
        else None
    )
    maxdd = abs(float(base["max_drawdown_pct"]))
    calmar = float(base["cagr_pct"]) / maxdd if maxdd > 1e-12 else None
    out = dict(base)
    out["calmar"] = calmar
    out["sortino"] = sortino
    out["positive_month_pct"] = 100 * float(np.mean(rs > 0)) if len(rs) else None
    return out


def trim_result(result, start):
    idx = [i for i, mo in enumerate(result["months"]) if mo >= start]
    if not idx:
        return {"months": [], "rets": [], "weights": []}
    return {
        "months": [result["months"][i] for i in idx],
        "rets": [result["rets"][i] for i in idx],
        "weights": [result["weights"][i] for i in idx],
    }


def result_metrics(result, start=None, cost_bps=10):
    q = trim_result(result, start) if start is not None else result
    return enhanced_metrics(q["months"], q["rets"], q["weights"], cost_bps)


def baseline_result(panel):
    months, rets, weights = [], [], []
    for row in panel:
        months.append(row["month"])
        rets.append(row["eq"] * row["er"] + row["debt"] * row["dr"])
        weights.append({"equity": row["eq"], "debt": row["debt"]})
    return {"months": months, "rets": rets, "weights": weights}


def metal_result(
    panel,
    sources,
    funding="proportional",
    static=None,
    ratio_obs=756,
    ratio_min_obs=250,
    robust_ratio=False,
    gold_drop=None,
    silver_drop=None,
    gold_weights=None,
    silver_weights=None,
    gold_center=13.0,
    gold_slope=5.0,
    silver_center=3.5,
    silver_slope=3.5,
):
    months, rets, weights = [], [], []
    first_eligible = None
    for row in panel:
        g = s = 0.0
        eligible = row["gold_c"] is not None and finite(row["gr"]) and finite(row["sr"])
        sc = None
        if eligible:
            if ratio_obs == 756 and ratio_min_obs == 250 and not robust_ratio:
                sc = row["silver_c"]
            else:
                sc = silver_components(
                    sources["gold"],
                    sources["silver"],
                    sources["mac"],
                    row["signal_date"],
                    ratio_obs=ratio_obs,
                    min_obs=ratio_min_obs,
                    robust_ratio=robust_ratio,
                )
            eligible = sc is not None
        if eligible:
            if static is not None:
                g, s = static
            else:
                target = target_from_components(
                    row["gold_c"],
                    sc,
                    gold_drop=gold_drop,
                    silver_drop=silver_drop,
                    gold_weights=gold_weights,
                    silver_weights=silver_weights,
                    gold_center=gold_center,
                    gold_slope=gold_slope,
                    silver_center=silver_center,
                    silver_slope=silver_slope,
                )
                if target is not None:
                    g, s = target[0], target[1]
                else:
                    eligible = False
        if eligible and first_eligible is None:
            first_eligible = row["month"]
        w = fund_metals(row["eq"], row["debt"], g, s, funding)
        r = (
            w["equity"] * row["er"]
            + w["debt"] * row["dr"]
            + w["gold"] * (row["gr"] if finite(row["gr"]) else 0.0)
            + w["silver"] * (row["sr"] if finite(row["sr"]) else 0.0)
        )
        months.append(row["month"])
        rets.append(r)
        weights.append(w)
    return {"months": months, "rets": rets, "weights": weights, "first_eligible": first_eligible}


def btc_components(btc_usd, mac, dt):
    feat = mb.rolling_price_features(btc_usd, dt)
    liq = mb.global_liquidity(mac, dt)
    if feat is None or not finite(liq):
        return None
    c = {
        "price_vs_200d": mb.squash(feat["vs_ma200_pct"], 20.0),
        "btc_12m_momentum": mb.squash(feat["momentum_12m_pct"], 60.0),
        "global_liquidity": float(liq),
        "drawdown_value": mb.squash((-feat["drawdown_3y_pct"]) - 25, 20.0),
    }
    score = (
        0.30 * c["price_vs_200d"]
        + 0.20 * c["btc_12m_momentum"]
        + 0.25 * c["global_liquidity"]
        + 0.25 * c["drawdown_value"]
    )
    if score < -0.50:
        target = 0.0
    elif score < -0.15:
        target = 0.025
    elif score < 0.25:
        target = 0.05
    elif score < 0.55:
        target = 0.075
    else:
        target = 0.10
    return {"components": c, "score": float(score), "target": target}


def load_panel():
    alloc = pd.read_csv(mb.ALLOC)
    alloc["month"] = pd.to_datetime(alloc.Date).dt.to_period("M")
    alloc = alloc.set_index("month")

    tri = mb.fs.nifty_tri_daily()
    tri_m = mb.first_monthly(tri)
    eq_nav, _ = mb.fs.mf_history(mb.fs.EQUITY_CODE)
    eq_m = mb.first_monthly(eq_nav)
    db_nav, _ = mb.fs.mf_history(mb.fs.DEBT_CODE)
    db_m = mb.first_monthly(db_nav)
    rates = mb.fs.short_rate_monthly()

    gold = mb.yahoo_history("GC=F", "1999-01-01")
    silver = mb.yahoo_history("SI=F", "1999-01-01")
    btc = mb.yahoo_history("BTC-USD", "2014-01-01")
    mac = mb.build_macro()
    gold_inr = mb.inr_series(gold, mac["fx"])
    silver_inr = mb.inr_series(silver, mac["fx"])
    btc_inr = mb.inr_series(btc, mac["fx"])

    panel = []
    months = pd.period_range("2000-01", pd.Period(date.today(), freq="M"), freq="M")
    for mo in months:
        if mo not in alloc.index:
            continue
        er = mb.equity_return(mo, eq_m, eq_nav, tri_m, tri)
        dr = mb.debt_return(mo, db_m, db_nav, rates)
        if not all(finite(x) for x in (er, dr)):
            continue
        gr = mb.monthly_return(gold_inr, mo)
        sr = mb.monthly_return(silver_inr, mo)
        br = mb.monthly_return(btc_inr, mo)
        eq = float(alloc.loc[mo, "Equity %"]) / 100.0
        debt = 1 - eq
        _, signal_date = mb.first_on_or_after(tri, mo.start_time, 12)
        signal_date = signal_date or mo.start_time
        gc = gold_components(gold, mac, signal_date)
        sc = silver_components(gold, silver, mac, signal_date, 756, 250, False)
        bc = btc_components(btc, mac, signal_date) if finite(br) else None
        panel.append(
            {
                "month": mo,
                "signal_date": signal_date,
                "eq": eq,
                "debt": debt,
                "er": float(er),
                "dr": float(dr),
                "gr": float(gr) if finite(gr) else None,
                "sr": float(sr) if finite(sr) else None,
                "br": float(br) if finite(br) else None,
                "gold_c": gc,
                "silver_c": sc,
                "btc_c": bc,
            }
        )
    if len(panel) < 250:
        raise RuntimeError(f"Insufficient audit history: {len(panel)} months")
    return panel, {"gold": gold, "silver": silver, "btc": btc, "mac": mac}


def common_start(*results):
    starts = [r.get("first_eligible") for r in results if r.get("first_eligible") is not None]
    return max(starts) if starts else None


def metric_summary(m):
    if m is None:
        return None
    keys = (
        "cagr_pct",
        "max_drawdown_pct",
        "annualized_volatility_pct",
        "calmar",
        "sortino",
        "average_monthly_turnover_pct",
        "months",
    )
    return {k: m.get(k) for k in keys}


def static_vs_dynamic(panel, sources, baseline):
    dynamic = metal_result(panel, sources)
    static_specs = {
        "static_gold_10": (0.10, 0.00),
        "static_gold_15": (0.15, 0.00),
        "static_gold10_silver5": (0.10, 0.05),
        "static_neutral_13_3_5": (0.13, 0.035),
    }
    statics = {k: metal_result(panel, sources, static=v) for k, v in static_specs.items()}
    start = common_start(dynamic)
    out = {
        "common_start": str(start),
        "baseline": metric_summary(result_metrics(baseline, start)),
        "dynamic_research_v1": metric_summary(result_metrics(dynamic, start)),
    }
    for k, r in statics.items():
        out[k] = metric_summary(result_metrics(r, start))
    d = out["dynamic_research_v1"]
    s = out["static_neutral_13_3_5"]
    out["dynamic_minus_static_neutral"] = {
        "cagr_pp": d["cagr_pct"] - s["cagr_pct"],
        "max_drawdown_pp": d["max_drawdown_pct"] - s["max_drawdown_pct"],
        "volatility_pp": d["annualized_volatility_pct"] - s["annualized_volatility_pct"],
        "calmar_delta": d["calmar"] - s["calmar"],
    }
    return out, dynamic


def funding_audit(panel, sources, baseline):
    variants = {
        mode: metal_result(panel, sources, funding=mode)
        for mode in ("proportional", "equity_first", "debt_first")
    }
    start = common_start(*variants.values())
    return {
        "common_start": str(start),
        "baseline": metric_summary(result_metrics(baseline, start)),
        "variants": {k: metric_summary(result_metrics(v, start)) for k, v in variants.items()},
    }


def lookback_audit(panel, sources, baseline):
    specs = {
        "live_3y_legacy": (756, 250, False),
        "3y_full": (756, 605, False),
        "5y": (1260, 1008, False),
        "7y": (1764, 1411, False),
        "10y": (2520, 2016, False),
        "expanding": (None, 756, False),
        "5y_robust_median_mad": (1260, 1008, True),
    }
    variants = {
        k: metal_result(
            panel,
            sources,
            ratio_obs=obs,
            ratio_min_obs=min_obs,
            robust_ratio=robust,
        )
        for k, (obs, min_obs, robust) in specs.items()
    }
    start = common_start(*variants.values())
    return {
        "common_start": str(start),
        "baseline": metric_summary(result_metrics(baseline, start)),
        "variants": {
            k: {
                "first_eligible": str(v["first_eligible"]),
                "performance": metric_summary(result_metrics(v, start)),
            }
            for k, v in variants.items()
        },
    }


def ablation_audit(panel, sources):
    full = metal_result(panel, sources)
    gold = {
        "full": full,
        **{"drop_" + factor: metal_result(panel, sources, gold_drop=factor) for factor in GOLD_WEIGHTS},
    }
    silver = {
        "full": full,
        **{"drop_" + factor: metal_result(panel, sources, silver_drop=factor) for factor in SILVER_WEIGHTS},
    }
    start = common_start(full)
    full_m = result_metrics(full, start)

    def pack(group):
        out = {}
        for k, v in group.items():
            m = result_metrics(v, start)
            out[k] = metric_summary(m)
            if k != "full":
                out[k]["delta_cagr_pp_vs_full"] = m["cagr_pct"] - full_m["cagr_pct"]
                out[k]["delta_calmar_vs_full"] = m["calmar"] - full_m["calmar"]
        return out

    return {"common_start": str(start), "gold": pack(gold), "silver": pack(silver)}


def perturbation_audit(panel, sources, baseline, full_dynamic, static_section):
    start = full_dynamic["first_eligible"]
    baseline_m = result_metrics(baseline, start)
    full_m = result_metrics(full_dynamic, start)
    static_m = static_section["static_neutral_13_3_5"]
    rng = random.Random(SEED)
    rows = []
    for _ in range(PERTURBATIONS):
        gw = {k: v * rng.uniform(0.8, 1.2) for k, v in GOLD_WEIGHTS.items()}
        sw = {k: v * rng.uniform(0.8, 1.2) for k, v in SILVER_WEIGHTS.items()}
        r = metal_result(
            panel,
            sources,
            gold_weights=gw,
            silver_weights=sw,
            gold_center=rng.uniform(11.5, 14.5),
            gold_slope=rng.uniform(4.0, 6.0),
            silver_center=rng.uniform(2.75, 4.25),
            silver_slope=rng.uniform(2.8, 4.2),
        )
        m = result_metrics(r, start)
        rows.append(
            {
                "cagr": m["cagr_pct"],
                "maxdd": m["max_drawdown_pct"],
                "vol": m["annualized_volatility_pct"],
                "calmar": m["calmar"],
            }
        )
    df = pd.DataFrame(rows)

    def dist(col):
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        return {
            "min": float(s.min()),
            "p10": float(s.quantile(0.10)),
            "median": float(s.median()),
            "p90": float(s.quantile(0.90)),
            "max": float(s.max()),
        }

    return {
        "seed": SEED,
        "variants": PERTURBATIONS,
        "perturbation_ranges": {
            "factor_weights": "each published weight multiplied independently by U(0.8,1.2), then renormalized",
            "gold_center_pct": [11.5, 14.5],
            "gold_slope_pct": [4.0, 6.0],
            "silver_center_pct": [2.75, 4.25],
            "silver_slope_pct": [2.8, 4.2],
            "allocation_clips": "unchanged at Gold 8-18%, Silver 0-7%",
        },
        "reference": {
            "baseline": metric_summary(baseline_m),
            "published_dynamic": metric_summary(full_m),
            "static_neutral_13_3_5": static_m,
        },
        "distribution": {
            "cagr_pct": dist("cagr"),
            "max_drawdown_pct": dist("maxdd"),
            "annualized_volatility_pct": dist("vol"),
            "calmar": dist("calmar"),
        },
        "pass_rates_pct": {
            "cagr_above_baseline": 100 * float((df.cagr > baseline_m["cagr_pct"]).mean()),
            "calmar_above_baseline": 100 * float((df.calmar > baseline_m["calmar"]).mean()),
            "calmar_above_static_neutral": 100 * float((df.calmar > static_m["calmar"]).mean()),
            "cagr_above_baseline_and_drawdown_no_worse": 100
            * float(((df.cagr > baseline_m["cagr_pct"]) & (df.maxdd >= baseline_m["max_drawdown_pct"])).mean()),
        },
    }


def btc_audit(panel, sources, full_dynamic):
    dyn_by_month = {
        mo: (r, w)
        for mo, r, w in zip(full_dynamic["months"], full_dynamic["rets"], full_dynamic["weights"])
    }
    rows = []
    for row in panel:
        bc = row["btc_c"]
        if bc is None or not finite(row["br"]) or row["month"] not in dyn_by_month:
            continue
        core_r, core_w = dyn_by_month[row["month"]]
        bw = float(bc["target"])
        btc_w = {k: float(v) * (1 - bw) for k, v in core_w.items()}
        btc_w["btc"] = bw
        funded_r = (1 - bw) * float(core_r) + bw * float(row["br"])
        rows.append((row, core_r, core_w, funded_r, btc_w, bc))
    if not rows:
        return {"status": "unavailable"}
    active = [x for x in rows if x[5]["target"] > 0]
    start = active[0][0]["month"] if active else rows[0][0]["month"]
    rows = [x for x in rows if x[0]["month"] >= start]
    months = [x[0]["month"] for x in rows]
    core_rets = [x[1] for x in rows]
    core_weights = [x[2] for x in rows]
    funded_rets = [x[3] for x in rows]
    funded_weights = [x[4] for x in rows]
    core_m = enhanced_metrics(months, core_rets, core_weights, 10)
    funded_m = enhanced_metrics(months, funded_rets, funded_weights, 10)
    buckets = {}
    opposition = 0
    eligible = 0
    for row, _, _, _, _, bc in rows:
        label = f"{100 * bc['target']:.1f}%"
        buckets.setdefault(label, []).append(float(row["br"]))
        mom = bc["components"]["btc_12m_momentum"]
        val = bc["components"]["drawdown_value"]
        if finite(mom) and finite(val):
            eligible += 1
            if float(mom) * float(val) < 0:
                opposition += 1
    bucket_stats = {}
    for k, vals in sorted(buckets.items()):
        s = pd.Series(vals, dtype=float)
        bucket_stats[k] = {
            "months": int(len(s)),
            "mean_btc_month_return_pct": 100 * float(s.mean()),
            "median_btc_month_return_pct": 100 * float(s.median()),
            "positive_btc_month_pct": 100 * float((s > 0).mean()),
        }
    return {
        "status": "complete",
        "period_start": str(start),
        "period_end": str(months[-1]),
        "core_without_funded_btc": metric_summary(core_m),
        "funded_btc_variant": metric_summary(funded_m),
        "signal_distribution": {k: v["months"] for k, v in bucket_stats.items()},
        "btc_return_by_signal": bucket_stats,
        "momentum_value_opposition_rate_pct": 100 * opposition / eligible if eligible else None,
        "note": "This isolates the BTC-available era; pre-BTC crises such as 2008 cannot determine the BTC variant's max drawdown.",
    }


def recommendation_gate(static, funding, lookback, ablation, perturb, btc):
    dyn = static["dynamic_research_v1"]
    sta = static["static_neutral_13_3_5"]
    dynamic_adds_value = (
        dyn["calmar"] is not None
        and sta["calmar"] is not None
        and dyn["calmar"] > sta["calmar"]
        and dyn["cagr_pct"] >= sta["cagr_pct"]
    )
    robust = perturb["pass_rates_pct"]["calmar_above_static_neutral"] >= 70
    return {
        "live_model_change_authorized": False,
        "dynamic_metals_evidence": (
            "supportive" if dynamic_adds_value and robust else "mixed" if dynamic_adds_value or robust else "insufficient"
        ),
        "rule": "The audit never edits live parameters. Any future change requires explicit review of these results plus the existing prospective walk-forward governance.",
        "key_checks": {
            "dynamic_beats_static_neutral_on_cagr_and_calmar": bool(dynamic_adds_value),
            "at_least_70pct_parameter_perturbations_beat_static_neutral_calmar": bool(robust),
            "funding_rules_compared": True,
            "ratio_lookbacks_compared": True,
            "factor_ablations_completed": True,
            "btc_post_2015_risk_isolated": btc.get("status") == "complete",
        },
    }


def build():
    panel, sources = load_panel()
    baseline = baseline_result(panel)
    static, full_dynamic = static_vs_dynamic(panel, sources, baseline)
    funding = funding_audit(panel, sources, baseline)
    lookback = lookback_audit(panel, sources, baseline)
    ablation = ablation_audit(panel, sources)
    perturb = perturbation_audit(panel, sources, baseline, full_dynamic, static)
    btc = btc_audit(panel, sources, full_dynamic)
    out = {
        "status": "complete",
        "schema_version": 1,
        "audit_version": "multiasset-robustness-v2",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "history_start": str(panel[0]["month"]),
        "history_end": str(panel[-1]["month"]),
        "months": len(panel),
        "live_model_changed": False,
        "static_vs_dynamic": static,
        "funding_rule_audit": funding,
        "gold_silver_ratio_lookback_audit": lookback,
        "factor_ablation": ablation,
        "parameter_perturbation": perturb,
        "btc_era_audit": btc,
        "decision_gate": recommendation_gate(static, funding, lookback, ablation, perturb, btc),
        "limitations": [
            "Base NIFTY allocation is the existing common-history valuation reconstruction, not a release-vintage reconstruction of the full modern V3.6 stack.",
            "Historical macro series are latest-revised rather than vintage releases.",
            "Gold/Silver/BTC returns use continuous Yahoo USD price series converted to synthetic INR with BIS USD/INR; they are not Indian ETF total-return series.",
            "Taxes, product expense ratios, tracking error and exit loads are excluded; metrics use a 10 bps one-way turnover sensitivity.",
            "Parameter perturbation is a stability test, not an optimizer and not permission to choose the best historical parameter set.",
        ],
    }
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, indent=2, allow_nan=False), encoding="utf-8")
    tmp.replace(OUT)
    return out


if __name__ == "__main__":
    x = build()
    print(
        json.dumps(
            {
                "status": x["status"],
                "months": x["months"],
                "dynamic_evidence": x["decision_gate"]["dynamic_metals_evidence"],
                "btc_status": x["btc_era_audit"]["status"],
            }
        )
    )
