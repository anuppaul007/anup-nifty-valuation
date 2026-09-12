#!/usr/bin/env python3
"""Subperiod stability audit for multi-asset funding and static-vs-dynamic choices.

This is a companion to multiasset_robustness.py. It deliberately does not alter
live parameters. Its purpose is to reject full-sample winners that depend on one
market era.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import pandas as pd

import multiasset_robustness as mr

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "multiasset_subperiod.json"


def slice_result(result, start, end):
    start = pd.Period(start, freq="M")
    end = pd.Period(end, freq="M")
    idx = [i for i, mo in enumerate(result["months"]) if start <= mo <= end]
    return {
        "months": [result["months"][i] for i in idx],
        "rets": [result["rets"][i] for i in idx],
        "weights": [result["weights"][i] for i in idx],
    }


def metrics(result, start, end):
    q = slice_result(result, start, end)
    if len(q["months"]) < 12:
        return None
    return mr.metric_summary(mr.enhanced_metrics(q["months"], q["rets"], q["weights"], 10))


def build():
    panel, sources = mr.load_panel()
    baseline = mr.baseline_result(panel)
    variants = {
        "baseline": baseline,
        "dynamic_proportional": mr.metal_result(panel, sources, funding="proportional"),
        "dynamic_equity_first": mr.metal_result(panel, sources, funding="equity_first"),
        "dynamic_debt_first": mr.metal_result(panel, sources, funding="debt_first"),
        "static_neutral_13_3_5": mr.metal_result(panel, sources, static=(0.13, 0.035)),
        "static_gold_15": mr.metal_result(panel, sources, static=(0.15, 0.0)),
    }
    latest = str(panel[-1]["month"])
    periods = {
        "2006_05_to_2012_12": ("2006-05", "2012-12"),
        "2013_01_to_2019_12": ("2013-01", "2019-12"),
        "2020_01_to_latest": ("2020-01", latest),
    }
    rows = {}
    equity_first_wins = {"cagr": 0, "calmar": 0, "lowest_volatility": 0}
    equity_first_vs_prop = []
    for label, (start, end) in periods.items():
        perf = {name: metrics(result, start, end) for name, result in variants.items()}
        eligible = {k: v for k, v in perf.items() if k != "baseline" and v is not None}
        best_cagr = max(eligible, key=lambda k: eligible[k]["cagr_pct"])
        best_calmar = max(eligible, key=lambda k: eligible[k]["calmar"])
        best_vol = min(eligible, key=lambda k: eligible[k]["annualized_volatility_pct"])
        equity_first_wins["cagr"] += int(best_cagr == "dynamic_equity_first")
        equity_first_wins["calmar"] += int(best_calmar == "dynamic_equity_first")
        equity_first_wins["lowest_volatility"] += int(best_vol == "dynamic_equity_first")
        eqf = perf["dynamic_equity_first"]
        prop = perf["dynamic_proportional"]
        equity_first_vs_prop.append(
            {
                "period": label,
                "cagr_delta_pp": eqf["cagr_pct"] - prop["cagr_pct"],
                "max_drawdown_delta_pp": eqf["max_drawdown_pct"] - prop["max_drawdown_pct"],
                "volatility_delta_pp": eqf["annualized_volatility_pct"] - prop["annualized_volatility_pct"],
                "calmar_delta": eqf["calmar"] - prop["calmar"],
            }
        )
        rows[label] = {
            "start": start,
            "end": end,
            "performance": perf,
            "best_nonbaseline": {
                "cagr": best_cagr,
                "calmar": best_calmar,
                "lowest_volatility": best_vol,
            },
        }
    consistent = sum(
        1
        for x in equity_first_vs_prop
        if x["cagr_delta_pp"] > 0 and x["calmar_delta"] > 0 and x["volatility_delta_pp"] <= 0
    )
    out = {
        "status": "complete",
        "schema_version": 1,
        "audit_version": "multiasset-subperiod-v2",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "live_model_changed": False,
        "periods": rows,
        "equity_first_best_count_out_of_3": equity_first_wins,
        "equity_first_vs_proportional": equity_first_vs_prop,
        "equity_first_consistent_advantage_periods_out_of_3": consistent,
        "decision": {
            "equity_first_candidate": bool(consistent >= 2),
            "live_change_authorized": False,
            "rule": "A retrospective subperiod winner is only a research candidate. Live funding changes still require explicit review and prospective governance.",
        },
        "limitations": [
            "Uses the same reconstructed NIFTY allocation history and latest-revised macro histories as the main robustness audit.",
            "Uses synthetic INR Gold/Silver returns rather than Indian ETF total-return histories.",
            "Three subperiods are a stability check, not an independent out-of-sample validation set.",
        ],
    }
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, indent=2, allow_nan=False), encoding="utf-8")
    tmp.replace(OUT)
    return out


if __name__ == "__main__":
    x = build()
    print(json.dumps({"status": x["status"], "consistent_periods": x["equity_first_consistent_advantage_periods_out_of_3"], "candidate": x["decision"]["equity_first_candidate"]}))
