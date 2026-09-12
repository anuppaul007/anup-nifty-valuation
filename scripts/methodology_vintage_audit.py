#!/usr/bin/env python3
"""Audit NIFTY valuation-methodology breaks and release-vintage coverage.

Research only. This script does not modify model.js, multiasset.py, latest.json,
or any prospective archived decision.

Why this exists
---------------
The published NIFTY 50 valuation history is not one homogeneous measurement:
* 31-Mar-2021: index P/E moved from standalone to consolidated trailing-4Q
  earnings (standalone fallback); dividend yield moved from annual-report
  dividend to rolling-12-month equity dividend based on ex-dividend date.
* 29-Sep-2023: index P/B moved from standalone annual-report net worth to
  consolidated annual-report net worth (standalone fallback).

Therefore a 2000-present backtest that applies today's fixed-reference constants
to the entire published ratio history is exploratory across methodology eras.
This audit measures the regime boundaries without fabricating a historical
"current-methodology" series.

The second part inventories release-vintage coverage. The long-history core does
not use the modern macro overlay, but a true historical full-model backtest would
need point-in-time vintages for revised/lagged macro series. ALFRED provides a
useful vintage archive for the OECD India 10Y series only from its FRED/ALFRED
availability period; that does not establish original 2011-2018 release vintages.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from io import StringIO
from pathlib import Path
import json
import math

import numpy as np
import pandas as pd
import requests

import update_data as b

ROOT = Path(__file__).resolve().parents[1]
SCREEN = ROOT / "data" / "monthly_signal_screen.json"
OUT = ROOT / "data" / "methodology_vintage_audit.json"

BREAKS = [
    {
        "id": "pe_dy_2021",
        "effective_date": "2021-03-31",
        "before_date": "2021-03-30",
        "after_date": "2021-03-31",
        "changed_fields": ["pe", "dy"],
        "source_url": "https://www.niftyindices.com/Press_Release/ind_prs23022021_1.pdf",
        "official_change": "P/E standalone trailing-4Q earnings -> consolidated trailing-4Q earnings (standalone fallback); dividend yield annual-report basis -> rolling-12-month equity dividends by ex-dividend date.",
        "confounder": "The effective date also coincides with index maintenance/rebalancing, so the adjacent-day published ratio jump is not a pure accounting bridge.",
    },
    {
        "id": "pb_2023",
        "effective_date": "2023-09-29",
        "before_date": "2023-09-28",
        "after_date": "2023-09-29",
        "changed_fields": ["pb"],
        "source_url": "https://www.niftyindices.com/Press_Release/ind_prs17082023.pdf",
        "official_change": "P/B standalone annual-report net worth -> consolidated annual-report net worth (standalone fallback).",
        "confounder": "The effective date coincides with semi-annual index reconstitution, so the adjacent-day published ratio jump is not a pure accounting bridge.",
    },
]

ERA_DEFS = {
    "era_A_legacy_all": {
        "label": "Before 31-Mar-2021: legacy P/E + P/B + dividend-yield definitions",
        "ratio_basis": {"pe": "standalone", "pb": "standalone", "dy": "annual-report dividend"},
    },
    "era_B_pe_dy_current_pb_legacy": {
        "label": "31-Mar-2021 through 28-Sep-2023: consolidated P/E, rolling-12m DY, legacy standalone P/B",
        "ratio_basis": {"pe": "consolidated", "pb": "standalone", "dy": "rolling-12m ex-dividend"},
    },
    "era_C_current_all": {
        "label": "29-Sep-2023 onward: current P/E + P/B + dividend-yield definitions",
        "ratio_basis": {"pe": "consolidated", "pb": "consolidated", "dy": "rolling-12m ex-dividend"},
    },
}

VINTAGE_MATRIX = {
    "india_10y_oecd": {
        "series": "INDIRLTLT01STM",
        "source": "OECD Main Economic Indicators via FRED/ALFRED",
        "observation_start": "2011-12",
        "alfred_revision_history_start": "2018-07-17",
        "status": "partial_vintage_archive",
        "implication": "ALFRED can test later vintages, but does not establish the original real-time publication path for 2011-2018.",
        "urls": [
            "https://fred.stlouisfed.org/series/INDIRLTLT01STM",
            "https://alfred.stlouisfed.org/series?seid=INDIRLTLT01STM",
        ],
    },
    "us_treasury_10y_and_real10y": {
        "source": "US Treasury daily curve",
        "status": "market_observation_history",
        "implication": "Daily market observations are dated; no historical full-model publication-vintage reconstruction is currently implemented.",
    },
    "vix": {
        "source": "CBOE daily VIX history",
        "status": "market_observation_history",
        "implication": "Dated market observations; no vintage problem comparable to revised macro releases, subject to vendor-history integrity.",
    },
    "brent": {
        "source": "Yahoo continuous Brent futures history",
        "status": "final_vendor_history",
        "implication": "Useful market proxy, but not an immutable point-in-time vendor vintage and includes continuous-contract construction.",
    },
    "fed_assets": {
        "source": "Federal Reserve H.4.1 / FRED WALCL fallback",
        "status": "vintage_reconstructible_not_implemented",
        "implication": "Weekly releases have historical vintages in principle; current retrospective work uses latest history unless separately frozen.",
    },
    "broad_usd": {
        "source": "Federal Reserve H.10 / FRED DTWEXBGS fallback",
        "status": "vintage_reconstructible_not_implemented",
        "implication": "Historical release/vintage path is not yet reconstructed in the model backtest.",
    },
    "bis_reer_usdinr": {
        "source": "BIS SDMX monthly series",
        "status": "unverified_release_vintage",
        "implication": "Monthly release lag/revisions are not reconstructed point-in-time.",
    },
    "india_cpi_iip": {
        "source": "MoSPI/NSO official PIB releases",
        "status": "current_release_verified_history_not_reconstructed",
        "implication": "Current observations use official release pages, but historical first-release vintages are not assembled for a full-model backtest.",
    },
    "india_repo": {
        "source": "RBI policy rate",
        "status": "effective_date_observable",
        "implication": "Policy changes can be mapped by effective date; this is substantially cleaner than revised macro series.",
    },
    "china_pmi": {
        "source": "National Bureau of Statistics of China release pages",
        "status": "current_release_verified_history_not_reconstructed",
        "implication": "Historical original release pages/vintages are not yet assembled across the full sample.",
    },
}

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FRED_SERIES = "INDIRLTLT01STM"
VINTAGE_SAMPLES = ["2018-07-17", "2019-07-17", "2020-07-17", "2021-07-17", "2022-07-17", "2023-07-17", "2024-07-17", "2025-07-17", "2026-07-17"]


def finite(x):
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def clip(x, lo, hi):
    return max(lo, min(hi, float(x)))


def era_for_date(d):
    dt = pd.Timestamp(d).normalize()
    if dt < pd.Timestamp("2021-03-31"):
        return "era_A_legacy_all"
    if dt < pd.Timestamp("2023-09-29"):
        return "era_B_pe_dy_current_pb_legacy"
    return "era_C_current_all"


def curve(z, k, zc):
    f = lambda x: 100.0 / (1.0 + math.exp(float(k) * float(x)))
    lo, hi = f(zc), f(-zc)
    return clip((f(z) - lo) / (hi - lo) * 100.0, 0.0, 100.0)


def calc_lenses(pe, pb, dy, gsec10, p):
    pe, pb, dy, gsec10 = map(float, (pe, pb, dy, gsec10))
    roe = 100.0 * pb / pe
    gap = 100.0 / pe - gsec10
    return {
        "pe": (pe - p["peM"]) / p["peS"],
        "pb_profitability_adjusted": (pb - p["pbM"]) / p["pbS"] - p["beta"] * (roe - p["roeM"]) / p["roeS"],
        "gap": -(gap - p["gapM"]) / p["gapS"],
        "dy": -(dy - p["dyM"]) / p["dyS"],
    }


def recompute(pe, pb, dy, gsec10, p):
    lenses = calc_lenses(pe, pb, dy, gsec10, p)
    z = (
        p["wPE"] * lenses["pe"]
        + p["wPB"] * lenses["pb_profitability_adjusted"]
        + p["wGAP"] * lenses["gap"]
        + p["wDY"] * lenses["dy"]
    ) / (p["wPE"] + p["wPB"] + p["wGAP"] + p["wDY"])
    return {"z": float(z), "core_equity": curve(z, p["k"], p["zc"]), "lenses": lenses}


def load_screen(path=SCREEN):
    x = json.loads(Path(path).read_text(encoding="utf-8"))
    if not x.get("records"):
        raise RuntimeError("monthly_signal_screen.json has no records")
    return x


def summarize_eras(records):
    groups = {k: [] for k in ERA_DEFS}
    for r in records:
        groups[era_for_date(r["nifty_asof"])].append(r)
    out = {}
    for key, rows in groups.items():
        if not rows:
            out[key] = {"definition": ERA_DEFS[key], "months": 0}
            continue
        def vals(name):
            return np.array([float(r[name]) for r in rows if finite(r.get(name))], dtype=float)
        eq, z = vals("core_equity"), vals("z")
        out[key] = {
            "definition": ERA_DEFS[key],
            "months": len(rows),
            "start_signal": rows[0]["signal_date"],
            "end_signal": rows[-1]["signal_date"],
            "start_observation": rows[0]["nifty_asof"],
            "end_observation": rows[-1]["nifty_asof"],
            "median_pe": float(np.median(vals("pe"))),
            "median_pb": float(np.median(vals("pb"))),
            "median_dy": float(np.median(vals("dy"))),
            "median_z": float(np.median(z)),
            "median_equity_pct": float(np.median(eq)),
            "equity_gt_80_count": int(np.sum(eq > 80.0)),
            "debt_gt_80_count": int(np.sum(eq < 20.0)),
            "equity_100_count": int(np.sum(np.isclose(eq, 100.0, atol=1e-12))),
            "debt_100_count": int(np.sum(np.isclose(eq, 0.0, atol=1e-12))),
        }
    return out


def _parse_ratio_rows(start, end):
    from jugaad_data.nse import index_pe_raw
    rows = index_pe_raw("NIFTY 50", pd.Timestamp(start).date(), pd.Timestamp(end).date())
    out = {}
    for x in rows or []:
        dt = b.pdate(b.pick(x, ["Date", "DATE", "HistoricalDate"]))
        pe = b.fnum(b.pick(x, ["P/E", "PE", "pe"]))
        pb = b.fnum(b.pick(x, ["P/B", "PB", "pb"]))
        dy = b.fnum(b.pick(x, ["Div Yield %", "Div Yield", "Dividend Yield", "DY", "divYield"]))
        if dt and all(finite(v) and float(v) > 0 for v in (pe, pb, dy)):
            out[str(pd.Timestamp(dt).date())] = {"pe": float(pe), "pb": float(pb), "dy": float(dy)}
    return out


def _parse_index_levels(start, end):
    from jugaad_data.nse import index_raw
    rows = index_raw("NIFTY 50", pd.Timestamp(start).date(), pd.Timestamp(end).date())
    out = {}
    for x in rows or []:
        dt = b.pdate(b.pick(x, ["Date", "DATE", "HistoricalDate", "Index Date"]))
        level = b.fnum(b.pick(x, ["CLOSE", "Close", "Closing Index Value", "Index Value", "INDEX_VALUE", "close"]))
        if dt and finite(level) and float(level) > 0:
            out[str(pd.Timestamp(dt).date())] = float(level)
    return out


def _screen_yield_for_observation(records, obs_date):
    exact = [r for r in records if r.get("nifty_asof") == obs_date]
    if exact:
        return float(exact[0]["gsec10"]), exact[0]["signal_date"]
    target = pd.Timestamp(obs_date)
    candidates = sorted(records, key=lambda r: abs((pd.Timestamp(r["nifty_asof"]) - target).days))
    if not candidates:
        raise RuntimeError("No screen record for break impact")
    return float(candidates[0]["gsec10"]), candidates[0]["signal_date"]


def price_adjusted_method_factor(field, before, after, price_ratio):
    if field in ("pe", "pb"):
        return (float(after[field]) / float(before[field])) / float(price_ratio)
    if field == "dy":
        return (float(after[field]) / float(before[field])) * float(price_ratio)
    raise ValueError(field)


def build_break_impacts(screen):
    p, records = screen["model_parameters"], screen["records"]
    out = []
    for spec in BREAKS:
        start = (pd.Timestamp(spec["before_date"]) - pd.Timedelta(days=5)).date()
        end = (pd.Timestamp(spec["after_date"]) + pd.Timedelta(days=5)).date()
        ratios = _parse_ratio_rows(start, end)
        levels = _parse_index_levels(start, end)
        before = ratios.get(spec["before_date"])
        after = ratios.get(spec["after_date"])
        if before is None or after is None:
            raise RuntimeError(f"Missing NIFTY ratios across methodology break {spec['id']}")
        if spec["before_date"] not in levels or spec["after_date"] not in levels:
            raise RuntimeError(f"Missing NIFTY levels across methodology break {spec['id']}")
        pr = levels[spec["after_date"]] / levels[spec["before_date"]]
        gsec, matched_signal = _screen_yield_for_observation(records, spec["after_date"])
        pre_calc = recompute(before["pe"], before["pb"], before["dy"], gsec, p)
        post_calc = recompute(after["pe"], after["pb"], after["dy"], gsec, p)
        out.append({
            **spec,
            "before": {**before, "nifty50": levels[spec["before_date"]]},
            "after": {**after, "nifty50": levels[spec["after_date"]]},
            "nifty_price_return_pct": 100.0 * (pr - 1.0),
            "price_adjusted_method_factors": {f: price_adjusted_method_factor(f, before, after, pr) for f in spec["changed_fields"]},
            "constant_gsec10_for_allocation_comparison": gsec,
            "matched_monthly_signal": matched_signal,
            "allocation_before_pct": pre_calc["core_equity"],
            "allocation_after_pct": post_calc["core_equity"],
            "allocation_jump_pp": post_calc["core_equity"] - pre_calc["core_equity"],
            "z_before": pre_calc["z"],
            "z_after": post_calc["z"],
            "z_jump": post_calc["z"] - pre_calc["z"],
            "lens_before": pre_calc["lenses"],
            "lens_after": post_calc["lenses"],
            "interpretation": "Adjacent published observations quantify the discontinuity seen by the model, but do not identify a pure accounting-methodology bridge because market moves and index maintenance can occur on the same effective date.",
        })
    return out


def era_backtests(screen):
    import protocol_backtest as pb
    panel, _ = pb.build_return_panel()
    targets = pd.Series(
        {pd.Period(pd.Timestamp(r["signal_date"]), freq="M"): float(r["core_equity"]) / 100.0 for r in screen["records"]},
        dtype=float,
    ).sort_index()
    out = {}
    for era in ERA_DEFS:
        months = [m for m in targets.index if era_for_date(m.to_timestamp(how="start")) == era]
        common = panel.index.intersection(pd.PeriodIndex(months, freq="M"))
        if not len(common):
            out[era] = {"months": 0}
            continue
        sim = pb.simulate(
            targets.loc[common],
            panel.loc[common, "equity_return"],
            panel.loc[common, "debt_conservative_cash"],
            band_pp=0,
            cost_bps=10,
        )
        out[era] = {
            "months": int(len(common)),
            "start_month": str(common.min()),
            "end_month": str(common.max()),
            "valuation_strategy": pb.metrics(sim),
            "nifty50_tri_buy_hold": pb.nifty_buy_hold(panel.loc[common, "equity_return"]),
            "warning": "Era-segment performance is descriptive. Short later eras are not validation samples and the target series still uses the stored historical yield convention.",
        }
    return out


def fred_vintage(vintage_date):
    params = {
        "id": FRED_SERIES,
        "cosd": "2011-12-01",
        "coed": str(date.today()),
        "vintage_date": vintage_date,
    }
    r = requests.get(FRED_CSV, params=params, timeout=30, headers={"User-Agent": "AnupNiftyValuation/3.6 research"})
    r.raise_for_status()
    q = pd.read_csv(StringIO(r.text))
    if q.shape[1] < 2:
        raise RuntimeError("FRED vintage CSV missing value column")
    q.columns = ["date", "value"] + list(q.columns[2:])
    q["date"] = pd.to_datetime(q["date"], errors="coerce")
    q["value"] = pd.to_numeric(q["value"], errors="coerce")
    return q.dropna(subset=["date", "value"]).sort_values("date").drop_duplicates("date")


def vintage_samples():
    result = {"series": FRED_SERIES, "status": "complete", "samples": [], "errors": []}
    current = None
    try:
        current = fred_vintage(str(date.today()))
    except Exception as e:
        result["status"] = "unavailable"
        result["errors"].append(f"current: {type(e).__name__}: {e}")
        return result
    current_by = current.set_index("date")["value"]
    for vd in VINTAGE_SAMPLES:
        try:
            q = fred_vintage(vd)
            if q.empty:
                raise RuntimeError("empty vintage")
            joined = q.set_index("date")["value"].to_frame("old").join(current_by.rename("current"), how="inner").dropna()
            max_rev = float((joined["current"] - joined["old"]).abs().max() * 100.0) if len(joined) else None
            result["samples"].append({
                "vintage_date": vd,
                "observations_available": int(len(q)),
                "first_observation": str(q.date.iloc[0].date()),
                "latest_observation": str(q.date.iloc[-1].date()),
                "latest_observation_age_days_at_vintage": int((pd.Timestamp(vd) - q.date.iloc[-1]).days),
                "max_abs_revision_bp_vs_current_on_overlap": max_rev,
            })
        except Exception as e:
            result["errors"].append(f"{vd}: {type(e).__name__}: {e}")
    if not result["samples"]:
        result["status"] = "unavailable"
    elif result["errors"]:
        result["status"] = "partial"
    return result


def build(run_network=True, run_backtest=True):
    screen = load_screen()
    eras = summarize_eras(screen["records"])
    breaks = build_break_impacts(screen) if run_network else None
    vintages = vintage_samples() if run_network else {"status": "skipped"}
    backtests = era_backtests(screen) if run_backtest else None
    out = {
        "status": "complete",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "research_only": True,
        "live_model_changed": False,
        "live_allocation_changed": False,
        "source_screen_generated_at": screen.get("generated_at"),
        "official_methodology_breaks": BREAKS,
        "methodology_eras": eras,
        "published_break_impacts": breaks,
        "era_backtests": backtests,
        "release_vintage_inventory": VINTAGE_MATRIX,
        "oecd_10y_alfred_sample": vintages,
        "core_conclusions": {
            "single_2000_present_current_definition_series_exists": False,
            "fully_current_ratio_definition_history_starts": "2023-09-29",
            "pe_and_dy_current_definition_history_starts": "2021-03-31",
            "can_rescale_prebreak_history_from_one_day_jump": False,
            "reason_not_to_bridge": "Both methodology changes coincide with market movement and index maintenance/reconstitution, and no simultaneous old/new definition history exists. A bridge would be an assumption, not observed data.",
            "full_modern_model_vintage_clean_backtest_available": False,
            "what_is_required": "For an apples-to-apples current-definition history, reconstruct constituent-level historical consolidated earnings/net worth and rolling-12m dividends with point-in-time index membership/free-float weights; for a full modern model backtest, also reconstruct original-release macro vintages.",
        },
        "governance": {
            "long_history_label": "exploratory cross-methodology evidence",
            "current_definition_evidence_label": "post-29-Sep-2023 only",
            "promotion_allowed": False,
            "live_parameters_unchanged": True,
        },
    }
    OUT.write_text(json.dumps(out, indent=2, allow_nan=False), encoding="utf-8")
    headline = {
        "era_months": {k: v.get("months") for k, v in eras.items()},
        "break_allocation_jumps_pp": {x["id"]: x["allocation_jump_pp"] for x in (breaks or [])},
        "oecd_vintage_status": vintages.get("status"),
        "full_current_definition_history_starts": out["core_conclusions"]["fully_current_ratio_definition_history_starts"],
        "live_model_changed": False,
    }
    print(json.dumps(headline, separators=(",", ":")))
    return out


if __name__ == "__main__":
    build()
