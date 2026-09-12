#!/usr/bin/env python3
"""Audit historical 10Y G-sec timing in the monthly valuation screen.

Research only. This script does not modify model.js, multiasset.py, latest.json,
or any prospective archived decision.

The incumbent V3.9 evidence screen uses a blanket two-calendar-month yield lag.
That is unnecessarily stale for RBI's archived *month-end transaction-yield*
observations: at a month-start decision made after the previous trading day's
close, the immediately preceding month-end market observation was already
observable. OECD monthly long-term yields are different: their historical
publication timing/vintages are not verified, so this audit does not silently
advance those observations in the point-in-time-safe challenger.

Outputs three variants:
  incumbent                  current screen exactly as stored
  rbi_timing_corrected       latest RBI SGL month-end observation strictly
                             before the signal; OECD timing left unchanged
  observation_date_only      latest observation strictly before signal across
                             RBI+OECD, explicitly NOT claimed point-in-time safe

It also optionally applies the three target series to the existing protocol
return panel (NIFTY TRI + conservative debt proxy, 10 bps one-way cost) to show
whether the timing choice is economically material. That is an exploratory
backtest, not a validation-policy promotion test.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import math

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCREEN = ROOT / "data" / "monthly_signal_screen.json"
OUT = ROOT / "data" / "gsec_timing_audit.json"

OFFICIAL_VERIFICATION = {
    "rbi_table_definition": "Month-end Yield of SGL Transactions in Government Dated Securities for Various Maturities",
    "interpretation": "The 10-year row is a month-end secondary-market transaction-yield observation, so its observation date is the month-end date rather than a later macro-release month.",
    "sources": [
        {
            "url": "https://www.rbi.org.in/scripts/PublicationsView.aspx?id=17320",
            "label": "RBI Handbook 2015-16, Table 187",
            "coverage_visible": "2013-14 to 2016-17",
        },
        {
            "url": "https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=22654",
            "label": "RBI Handbook 2023-24, Table 180",
            "coverage_visible": "2021-22 to 2024-25 partial",
        },
    ],
    "availability_convention": "Decision timestamp is after the previous trading-day close and before the first trading session of the new month; therefore the previous month-end market observation is eligible when it exists.",
}


def finite(x):
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def clip(x, lo, hi):
    return max(lo, min(hi, float(x)))


def curve(z, k, zc):
    f = lambda x: 100.0 / (1.0 + math.exp(float(k) * float(x)))
    lo = f(zc)
    hi = f(-zc)
    return clip((f(z) - lo) / (hi - lo) * 100.0, 0.0, 100.0)


def recompute(pe, pb, dy, gsec10, p):
    pe, pb, dy, gsec10 = map(float, (pe, pb, dy, gsec10))
    roe = 100.0 * pb / pe
    gap = 100.0 / pe - gsec10
    z_pe = (pe - p["peM"]) / p["peS"]
    z_pb = (pb - p["pbM"]) / p["pbS"] - p["beta"] * (roe - p["roeM"]) / p["roeS"]
    z_gap = -(gap - p["gapM"]) / p["gapS"]
    z_dy = -(dy - p["dyM"]) / p["dyS"]
    num = p["wPE"] * z_pe + p["wPB"] * z_pb + p["wGAP"] * z_gap + p["wDY"] * z_dy
    den = p["wPE"] + p["wPB"] + p["wGAP"] + p["wDY"]
    z = num / den
    return {
        "z": z,
        "core_equity": curve(z, p["k"], p["zc"]),
        "core_debt": 100.0 - curve(z, p["k"], p["zc"]),
        "earnings_yield_minus_gsec": gap,
    }


def load_screen(path=SCREEN):
    x = json.loads(Path(path).read_text(encoding="utf-8"))
    if not x.get("records"):
        raise RuntimeError("monthly_signal_screen.json has no records")
    return x


def is_rbi_record(r):
    text = " ".join(str(r.get(k, "")) for k in ("yield_source", "yield_basis")).lower()
    return "rbi.org.in" in text or "rbi sgl" in text


def observation_pool(records, rbi_only=False):
    pool = {}
    for r in records:
        if rbi_only and not is_rbi_record(r):
            continue
        dt = pd.Timestamp(r["gsec_asof"]).normalize()
        item = {
            "date": dt,
            "gsec10": float(r["gsec10"]),
            "yield_source": r.get("yield_source"),
            "yield_basis": r.get("yield_basis"),
            "is_rbi": is_rbi_record(r),
        }
        old = pool.get(dt)
        if old is None or (item["is_rbi"] and not old["is_rbi"]):
            pool[dt] = item
    return sorted(pool.values(), key=lambda x: x["date"])


def latest_before(pool, signal_date):
    sd = pd.Timestamp(signal_date).normalize()
    eligible = [x for x in pool if x["date"] < sd]
    return eligible[-1] if eligible else None


def build_variants(screen):
    p = screen["model_parameters"]
    records = screen["records"]
    rbi_pool = observation_pool(records, rbi_only=True)
    all_pool = observation_pool(records, rbi_only=False)
    variants = {"incumbent": [], "rbi_timing_corrected": [], "observation_date_only": []}

    max_recompute_z_diff = 0.0
    max_recompute_eq_diff = 0.0

    for r in records:
        base_calc = recompute(r["pe"], r["pb"], r["dy"], r["gsec10"], p)
        max_recompute_z_diff = max(max_recompute_z_diff, abs(base_calc["z"] - float(r["z"])))
        max_recompute_eq_diff = max(max_recompute_eq_diff, abs(base_calc["core_equity"] - float(r["core_equity"])))

        incumbent = dict(r)
        incumbent["timing_variant"] = "incumbent"
        variants["incumbent"].append(incumbent)

        if is_rbi_record(r):
            obs = latest_before(rbi_pool, r["signal_date"])
        else:
            obs = None
        safe_obs = obs or {
            "date": pd.Timestamp(r["gsec_asof"]),
            "gsec10": float(r["gsec10"]),
            "yield_source": r.get("yield_source"),
            "yield_basis": r.get("yield_basis"),
            "is_rbi": is_rbi_record(r),
        }
        calc = recompute(r["pe"], r["pb"], r["dy"], safe_obs["gsec10"], p)
        safe = dict(r)
        safe.update(calc)
        safe.update({
            "gsec_asof": str(safe_obs["date"].date()),
            "gsec10": safe_obs["gsec10"],
            "yield_source": safe_obs["yield_source"],
            "yield_basis": safe_obs["yield_basis"],
            "timing_variant": "rbi_timing_corrected",
            "timing_changed": str(safe_obs["date"].date()) != str(r["gsec_asof"]),
        })
        variants["rbi_timing_corrected"].append(safe)

        obs2 = latest_before(all_pool, r["signal_date"])
        if obs2 is None:
            obs2 = safe_obs
        calc2 = recompute(r["pe"], r["pb"], r["dy"], obs2["gsec10"], p)
        allv = dict(r)
        allv.update(calc2)
        allv.update({
            "gsec_asof": str(obs2["date"].date()),
            "gsec10": obs2["gsec10"],
            "yield_source": obs2["yield_source"],
            "yield_basis": obs2["yield_basis"],
            "timing_variant": "observation_date_only",
            "timing_changed": str(obs2["date"].date()) != str(r["gsec_asof"]),
        })
        variants["observation_date_only"].append(allv)

    return variants, {
        "max_abs_incumbent_recompute_z_diff": max_recompute_z_diff,
        "max_abs_incumbent_recompute_equity_diff_pp": max_recompute_eq_diff,
        "rbi_observation_count": len(rbi_pool),
        "all_observation_count": len(all_pool),
    }


def bucket(eq):
    eq = float(eq)
    if eq > 80.0:
        return "equity_gt_80"
    if eq < 20.0:
        return "debt_gt_80"
    return "middle"


def compare(base, challenger):
    if len(base) != len(challenger):
        raise RuntimeError("variant length mismatch")
    rows = []
    for a, b in zip(base, challenger):
        if a["signal_date"] != b["signal_date"]:
            raise RuntimeError("variant date mismatch")
        rows.append({
            "signal_date": a["signal_date"],
            "incumbent_gsec_asof": a["gsec_asof"],
            "challenger_gsec_asof": b["gsec_asof"],
            "incumbent_gsec10": float(a["gsec10"]),
            "challenger_gsec10": float(b["gsec10"]),
            "z_delta": float(b["z"]) - float(a["z"]),
            "equity_delta_pp": float(b["core_equity"]) - float(a["core_equity"]),
            "incumbent_equity": float(a["core_equity"]),
            "challenger_equity": float(b["core_equity"]),
            "incumbent_bucket": bucket(a["core_equity"]),
            "challenger_bucket": bucket(b["core_equity"]),
            "methodology_era": a.get("methodology_era"),
        })
    changed = [x for x in rows if x["incumbent_gsec_asof"] != x["challenger_gsec_asof"]]
    crossings = [x for x in rows if x["incumbent_bucket"] != x["challenger_bucket"]]
    largest = sorted(rows, key=lambda x: abs(x["equity_delta_pp"]), reverse=True)[:20]
    abs_z = [abs(x["z_delta"]) for x in rows]
    abs_eq = [abs(x["equity_delta_pp"]) for x in rows]
    return {
        "months": len(rows),
        "timing_changed_months": len(changed),
        "max_abs_z_delta": max(abs_z) if abs_z else 0.0,
        "mean_abs_z_delta": sum(abs_z) / len(abs_z) if abs_z else 0.0,
        "max_abs_equity_delta_pp": max(abs_eq) if abs_eq else 0.0,
        "mean_abs_equity_delta_pp": sum(abs_eq) / len(abs_eq) if abs_eq else 0.0,
        "bucket_crossing_count": len(crossings),
        "bucket_crossings": crossings,
        "incumbent_counts": {
            "equity_gt_80": sum(bucket(x["core_equity"]) == "equity_gt_80" for x in base),
            "debt_gt_80": sum(bucket(x["core_equity"]) == "debt_gt_80" for x in base),
            "saturated_equity_100": sum(abs(float(x["core_equity"]) - 100.0) < 1e-12 for x in base),
            "saturated_debt_100": sum(abs(float(x["core_equity"])) < 1e-12 for x in base),
        },
        "challenger_counts": {
            "equity_gt_80": sum(bucket(x["core_equity"]) == "equity_gt_80" for x in challenger),
            "debt_gt_80": sum(bucket(x["core_equity"]) == "debt_gt_80" for x in challenger),
            "saturated_equity_100": sum(abs(float(x["core_equity"]) - 100.0) < 1e-12 for x in challenger),
            "saturated_debt_100": sum(abs(float(x["core_equity"])) < 1e-12 for x in challenger),
        },
        "largest_equity_shifts": largest,
    }


def backtest_variants(variants):
    import protocol_backtest as pb

    panel, _ = pb.build_return_panel()
    debt = panel["debt_conservative_cash"]
    eqret = panel["equity_return"]
    out = {}
    for name, records in variants.items():
        targets = pd.Series(
            {pd.Period(pd.Timestamp(r["signal_date"]), freq="M"): float(r["core_equity"]) / 100.0 for r in records},
            dtype=float,
        ).sort_index()
        common = panel.index.intersection(targets.index)
        sim = pb.simulate(targets.loc[common], eqret.loc[common], debt.loc[common], band_pp=0, cost_bps=10)
        out[name] = pb.metrics(sim)
    return out


def build(run_backtest=True):
    screen = load_screen()
    variants, integrity = build_variants(screen)
    safe_cmp = compare(variants["incumbent"], variants["rbi_timing_corrected"])
    obs_cmp = compare(variants["incumbent"], variants["observation_date_only"])
    result = {
        "status": "complete",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "research_only": True,
        "live_model_changed": False,
        "live_allocation_changed": False,
        "source_screen_generated_at": screen.get("generated_at"),
        "source_screen_scope": screen.get("scope"),
        "incumbent_yield_rule": screen.get("yield_rule"),
        "official_rbi_verification": OFFICIAL_VERIFICATION,
        "integrity": integrity,
        "variant_definitions": {
            "incumbent": "Stored V3.9 two-calendar-month yield timing.",
            "rbi_timing_corrected": "For RBI SGL month-end rows only, use the latest archived RBI month-end observation strictly before the month-start signal. OECD rows remain at incumbent timing because release timing/vintages are unverified.",
            "observation_date_only": "Use the latest stored yield observation strictly before signal across RBI and OECD. This is a sensitivity bound only and is NOT point-in-time safe for OECD monthly data without publication-vintage verification.",
        },
        "comparisons": {
            "rbi_timing_corrected_vs_incumbent": safe_cmp,
            "observation_date_only_vs_incumbent": obs_cmp,
        },
        "backtest": backtest_variants(variants) if run_backtest else None,
        "backtest_basis": "Exploratory fixed-core screen only; NIFTY 50 TRI, conservative debt proxy, 0pp band, 10bps one-way turnover cost. Not the full modern macro/earnings model and not the validation policy's daily-drawdown protocol.",
        "promotion_rule": "No automatic live-model change. A historical timing correction may replace the evidence screen only after source coverage and point-in-time assumptions are explicit and tests pass.",
    }
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-backtest", action="store_true")
    args = ap.parse_args()
    result = build(run_backtest=not args.no_backtest)
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    headline = {
        "status": result["status"],
        "safe_timing": {k: result["comparisons"]["rbi_timing_corrected_vs_incumbent"][k] for k in (
            "timing_changed_months", "max_abs_z_delta", "max_abs_equity_delta_pp", "bucket_crossing_count"
        )},
        "backtest": result["backtest"],
    }
    print(json.dumps(headline, separators=(",", ":")))


if __name__ == "__main__":
    main()
