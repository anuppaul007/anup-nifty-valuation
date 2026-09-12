#!/usr/bin/env python3
"""Exploratory protocol-style backtest for the Jan-2000 valuation screen.

Research only. This does not alter model.js, the live V3.6 allocation, or any
prospective archived decision.

What this adds over the older long-history result:
* NIFTY 50 Total Return Index for the equity sleeve.
* Explicit pre-2006 debt-proxy sensitivity instead of one hidden assumption.
* Drift-aware rebalancing.
* Rebalance bands (0/5/10 percentage points).
* One-way turnover cost sensitivity (0/10/25 bps).
* 60/40 annual-rebalance and NIFTY TRI buy-and-hold benchmarks.

Important limitations:
* The allocation signal remains the common-history valuation reconstruction,
  not the full modern V3.6 macro/earnings model.
* Historical macro/release vintages are not verified point-in-time.
* The pre-Apr-2006 debt variants are accrual proxies, not investable total-
  return indices. Actual debt-fund NAVs are used from Apr-2006 onward.
* Metrics are monthly. The validation policy's primary daily-drawdown metric is
  therefore not satisfied by this exploratory report.
"""
from __future__ import annotations

from datetime import date, timezone, datetime
from pathlib import Path
import json
import math

import numpy as np
import pandas as pd

import fund_strategy_rank as fs

ROOT = Path(__file__).resolve().parents[1]
ALLOC = ROOT / "data" / "backtest_monthly_2000.csv"
RATE_CACHE = ROOT / "data" / "india_short_rate_proxy_1999_2006.csv"
OUT = ROOT / "data" / "protocol_backtest.json"

COST_GRID_BPS = (0, 10, 25)
BAND_GRID_PP = (0, 5, 10)

RATE_AUDIT = {
    "cached_short_rate": {
        "file": "data/india_short_rate_proxy_1999_2006.csv",
        "identity": "OECD/FRED India short-term interest-rate observations cached for reproducibility",
        "not": "RBI policy repo rate",
        "role": "pre-Apr-2006 debt-return accrual proxy only",
        "source_urls": [
            "https://fred.stlouisfed.org/series/INDLOCOSTORSTM",
            "https://data-explorer.oecd.org/",
        ],
    },
    "rbi_policy_display": {
        "file": "data/backtest_monthly_2000.csv",
        "identity": "RBI repo/policy/LAF rate in force on the displayed calendar first day",
        "role": "historical display and sensitivity proxy; it is not an input to valuation_z",
        "source_note": "scripts/backtest_monthly_2000.py contains the effective-date history and nomenclature warning",
    },
    "rbi_91d_tbill_check": {
        "status": "partial_verified_not_used_for_full_period",
        "verified_annual_weighted_average_cutoff_yields_pct": {
            "2001-02": 6.88,
            "2002-03": 5.73,
            "2003-04": 4.63,
        },
        "source_urls": [
            "https://www.rbi.org.in/scripts/AnnualReportPublications.aspx?Id=344",
            "https://www.rbi.org.in/Upload/AnnualReport/Pdfs/56232.pdf",
        ],
        "reason_not_used": "A clean month-by-month 2000-2006 auction-derived total-return series has not yet been reconstructed and should not be fabricated from partial annual observations.",
    },
}


def finite(x):
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def load_alloc():
    q = pd.read_csv(ALLOC)
    q["month"] = pd.to_datetime(q["Date"]).dt.to_period("M")
    q = q.drop_duplicates("month").set_index("month").sort_index()
    q["target_equity"] = pd.to_numeric(q["Equity %"], errors="coerce") / 100.0
    q["policy_rate_pct"] = pd.to_numeric(q["RBI Repo Rate %"], errors="coerce")
    return q


def load_cached_short_rate():
    q = pd.read_csv(RATE_CACHE)
    q["month"] = pd.PeriodIndex(q["month"].astype(str), freq="M")
    q["rate_pct"] = pd.to_numeric(q["rate_pct"], errors="coerce")
    return q.dropna().drop_duplicates("month").set_index("month").rate_pct.astype(float).sort_index()


def annual_rate_return(rate_pct):
    return (1.0 + float(rate_pct) / 100.0) ** (1.0 / 12.0) - 1.0


def conservative_rate_pct(oecd_rate, policy_rate, haircut_pp=1.0):
    vals = [float(x) for x in (oecd_rate, policy_rate) if finite(x)]
    if not vals:
        return None
    return max(0.0, min(vals) - float(haircut_pp))


def first_monthly(s):
    return s.sort_index().groupby(s.index.to_period("M")).first()


def sleeve_return(month, monthly, daily):
    nm = month + 1
    if month not in monthly.index:
        return None
    start = float(monthly.loc[month])
    if nm in monthly.index:
        return float(monthly.loc[nm]) / start - 1.0
    end = float(daily.iloc[-1])
    return end / start - 1.0


def build_return_panel():
    alloc = load_alloc()
    rates = load_cached_short_rate()
    tri = fs.nifty_tri_daily()
    debt_nav, debt_meta = fs.mf_history(fs.DEBT_CODE)
    tri_m, debt_m = first_monthly(tri), first_monthly(debt_nav)

    rows = []
    for mo, a in alloc.iterrows():
        er = sleeve_return(mo, tri_m, tri)
        if er is None or not finite(er):
            continue

        if mo in debt_m.index:
            dr = sleeve_return(mo, debt_m, debt_nav)
            if dr is None or not finite(dr):
                continue
            debt = {k: float(dr) for k in ("oecd_short_rate", "rbi_policy_rate", "conservative_cash")}
            debt_source = "ICICI Prudential Short Term Fund Regular Growth NAV"
        else:
            prev = mo - 1
            oecd = rates.get(prev, np.nan)
            policy = alloc["policy_rate_pct"].get(prev, np.nan)
            if not finite(oecd) or not finite(policy):
                continue
            cons = conservative_rate_pct(oecd, policy, 1.0)
            debt = {
                "oecd_short_rate": annual_rate_return(oecd),
                "rbi_policy_rate": annual_rate_return(policy),
                "conservative_cash": annual_rate_return(cons),
            }
            debt_source = "pre-inception accrual proxy"

        rows.append(
            {
                "month": mo,
                "target_equity": float(a["target_equity"]),
                "equity_return": float(er),
                "debt_source": debt_source,
                **{f"debt_{k}": v for k, v in debt.items()},
            }
        )
    if not rows:
        raise RuntimeError("No common monthly return panel")
    panel = pd.DataFrame(rows).set_index("month").sort_index()
    return panel, debt_meta


def simulate(target, eq_ret, debt_ret, band_pp=0.0, cost_bps=0.0):
    """Simulate drift-aware monthly allocation.

    At each month-start, compare the target weight with the portfolio weight
    drifted from the prior month. Rebalance only when the absolute gap is at
    least the selected band. Cost is one-way turnover x cost_bps. Initial
    deployment starts at the first target and is not charged as turnover.
    """
    band = float(band_pp) / 100.0
    cost_rate = float(cost_bps) / 10000.0
    wealth = 1.0
    current_w = None
    turnover_sum = 0.0
    series = []
    rebalances = 0

    for mo in target.index:
        tw = float(target.loc[mo])
        er = float(eq_ret.loc[mo])
        dr = float(debt_ret.loc[mo])
        if current_w is None:
            w = tw
            turnover = 0.0
        else:
            gap = abs(tw - current_w)
            do_rebalance = (band <= 0.0) or (gap >= band - 1e-15)
            if do_rebalance:
                turnover = gap
                w = tw
                rebalances += 1
            else:
                turnover = 0.0
                w = current_w

        cost = wealth * turnover * cost_rate
        wealth_after_cost = wealth - cost
        gross_factor = w * (1.0 + er) + (1.0 - w) * (1.0 + dr)
        if gross_factor <= 0:
            raise RuntimeError("Non-positive portfolio factor")
        wealth = wealth_after_cost * gross_factor
        end_w = (w * (1.0 + er)) / gross_factor
        turnover_sum += turnover
        series.append((mo, wealth, w, end_w, turnover, cost))
        current_w = end_w

    return {
        "timeline": series,
        "ending_multiple": wealth,
        "one_way_turnover": turnover_sum,
        "rebalances": rebalances,
    }


def metrics(sim):
    t = sim["timeline"]
    if not t:
        raise RuntimeError("Empty simulation")
    idx = pd.PeriodIndex([x[0] for x in t], freq="M")
    wealth = pd.Series([x[1] for x in t], index=idx, dtype=float)
    rets = wealth.pct_change()
    rets.iloc[0] = wealth.iloc[0] - 1.0
    months = len(wealth)
    cagr = wealth.iloc[-1] ** (12.0 / months) - 1.0
    dd = wealth / wealth.cummax() - 1.0
    vol = rets.std(ddof=0) * math.sqrt(12.0)
    annual = (1.0 + rets).groupby(rets.index.year).prod() - 1.0
    worst_year = int(annual.idxmin()) if len(annual) else None
    return {
        "months": months,
        "multiple_x": float(wealth.iloc[-1]),
        "cagr_pct": 100.0 * float(cagr),
        "max_monthly_drawdown_pct": 100.0 * float(dd.min()),
        "annualized_monthly_volatility_pct": 100.0 * float(vol),
        "worst_calendar_year": worst_year,
        "worst_calendar_year_return_pct": 100.0 * float(annual.min()) if len(annual) else None,
        "average_monthly_one_way_turnover_pct": 100.0 * sim["one_way_turnover"] / months,
        "rebalance_count": int(sim["rebalances"]),
    }


def nifty_buy_hold(eq_ret):
    w = (1.0 + eq_ret).cumprod()
    sim = {
        "timeline": [(mo, float(v), 1.0, 1.0, 0.0, 0.0) for mo, v in w.items()],
        "ending_multiple": float(w.iloc[-1]),
        "one_way_turnover": 0.0,
        "rebalances": 0,
    }
    return metrics(sim)


def fixed_6040_annual(eq_ret, debt_ret, cost_bps=10.0):
    cost_rate = float(cost_bps) / 10000.0
    wealth = 1.0
    current_w = None
    turnover_sum = 0.0
    rebalances = 0
    series = []
    for mo in eq_ret.index:
        er = float(eq_ret.loc[mo]); dr = float(debt_ret.loc[mo])
        if current_w is None:
            w = 0.6; turnover = 0.0
        elif mo.month == 1:
            turnover = abs(0.6 - current_w); w = 0.6; rebalances += 1
        else:
            turnover = 0.0; w = current_w
        cost = wealth * turnover * cost_rate
        wealth_after_cost = wealth - cost
        factor = w * (1 + er) + (1 - w) * (1 + dr)
        wealth = wealth_after_cost * factor
        end_w = w * (1 + er) / factor
        turnover_sum += turnover
        series.append((mo, wealth, w, end_w, turnover, cost))
        current_w = end_w
    return metrics({"timeline": series, "ending_multiple": wealth, "one_way_turnover": turnover_sum, "rebalances": rebalances})


def main():
    panel, debt_meta = build_return_panel()
    target = panel["target_equity"]
    eq = panel["equity_return"]

    scenarios = {}
    for debt_name in ("oecd_short_rate", "rbi_policy_rate", "conservative_cash"):
        dr = panel[f"debt_{debt_name}"]
        debt_results = {}
        for band in BAND_GRID_PP:
            for cost in COST_GRID_BPS:
                key = f"band_{band}pp_cost_{cost}bps"
                debt_results[key] = metrics(simulate(target, eq, dr, band, cost))
        scenarios[debt_name] = debt_results

    baseline_key = "band_0pp_cost_10bps"
    out = {
        "status": "complete",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "research_label": "exploratory; historical release vintages and pre-2021 NIFTY valuation methodology are not fully comparable/verified",
        "live_model_changed": False,
        "live_allocation_changed": False,
        "period": {"start_month": str(panel.index.min()), "end_month": str(panel.index.max()), "months": int(len(panel))},
        "methodology": {
            "signal": "data/backtest_monthly_2000.csv common-history valuation screen",
            "equity_return": "NIFTY 50 Total Return Index",
            "debt_from_apr_2006": debt_meta.get("scheme_name") or "ICICI Prudential Short Term Fund Regular Growth NAV",
            "pre_apr_2006_debt_variants": {
                "oecd_short_rate": "prior-month cached OECD/FRED India short-term rate, accrued monthly",
                "rbi_policy_rate": "prior-month RBI repo/policy/LAF rate displayed by the historical screen, accrued monthly; sensitivity only, not investable total return",
                "conservative_cash": "max(0, min(OECD short rate, RBI policy/LAF rate) - 1 percentage point), accrued monthly",
            },
            "rebalancing": "drift-aware at month-start; rebalance only if target gap reaches selected band",
            "rebalance_bands_pp": list(BAND_GRID_PP),
            "one_way_cost_grid_bps": list(COST_GRID_BPS),
            "initial_deployment_cost": "not charged; only subsequent reallocations incur turnover cost",
            "metric_frequency": "monthly; not the validation policy's primary daily-drawdown test",
        },
        "rate_proxy_audit": RATE_AUDIT,
        "benchmarks": {
            "nifty50_tri_buy_hold": nifty_buy_hold(eq),
            "60_40_annual_rebalance_10bps_by_debt_variant": {
                name: fixed_6040_annual(eq, panel[f"debt_{name}"], 10.0)
                for name in ("oecd_short_rate", "rbi_policy_rate", "conservative_cash")
            },
        },
        "scenarios": scenarios,
        "headline": {
            "selected_for_comparison": baseline_key,
            "valuation_strategy": {name: scenarios[name][baseline_key] for name in scenarios},
            "nifty50_tri_buy_hold": nifty_buy_hold(eq),
        },
        "interpretation_guardrail": "This report is a robustness/sensitivity study. Do not promote parameters or change the live allocator from these retrospective results alone.",
    }
    OUT.write_text(json.dumps(out, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(out["headline"], separators=(",", ":")))


if __name__ == "__main__":
    main()
