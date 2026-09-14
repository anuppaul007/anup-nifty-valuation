#!/usr/bin/env python3
"""Deterministic six-month development reconstruction engine.

Research only; zero live authority. This module deliberately cannot fetch or
accept holdout targets. It evaluates only the frozen visible development window
(2023-09 through 2024-02) using complete 50-constituent point-in-time rows and
the already-frozen signed-denominator aggregation algebra.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable

from current_definition_aggregation import (
    aggregate_from_point_in_time_inputs,
    strict_month_inputs_complete,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "development_accounting_semantics_policy_v1.json"
POLICY = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

DEVELOPMENT_MONTHS = tuple(POLICY["scope"]["development_months"])
GATE = POLICY["development_candidate_reproduction_gate"]
HOLDOUT_START = "2024-03"


class DevelopmentReconstructionError(ValueError):
    """Raised when a development reconstruction violates a frozen gate."""


def _finite_number(value: object, name: str) -> float:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise DevelopmentReconstructionError(f"{name} must be finite")
    return float(value)


def assert_development_month(month: str) -> str:
    month = str(month)
    if month not in DEVELOPMENT_MONTHS:
        if month >= HOLDOUT_START:
            raise DevelopmentReconstructionError(
                f"holdout month {month} is sealed; development engine refuses it"
            )
        raise DevelopmentReconstructionError(f"month {month} is outside frozen development window")
    return month


def _unique_symbols(rows: list[dict]) -> None:
    symbols = [str(r.get("symbol") or "").strip() for r in rows]
    if any(not s for s in symbols):
        raise DevelopmentReconstructionError("every constituent row requires a symbol")
    if len(symbols) != len(set(symbols)):
        raise DevelopmentReconstructionError("duplicate constituent symbol")


def reconstruct_month(month: str, rows: Iterable[dict]) -> dict:
    """Reconstruct one frozen development month from exactly 50 complete rows."""
    month = assert_development_month(month)
    rows = list(rows)
    _unique_symbols(rows)
    complete, reason = strict_month_inputs_complete(
        rows,
        expected_members=50,
        min_weight_sum=0.985,
    )
    if not complete:
        raise DevelopmentReconstructionError(f"{month}: incomplete constituent panel: {reason}")

    result = aggregate_from_point_in_time_inputs(
        weights=[r["weight"] for r in rows],
        market_cap=[r["market_cap"] for r in rows],
        ttm_earnings=[r["ttm_earnings"] for r in rows],
        book_value=[r["book_value"] for r in rows],
        rolling_12m_dividends=[r["rolling_12m_dividends"] for r in rows],
    )
    return {
        "month": month,
        "constituents": 50,
        "status": "reconstructed",
        "research_only": True,
        "live_authority": "none",
        "pe": result["pe"],
        "pe_publishable": result["pe_publishable"],
        "pb": result["pb"],
        "dividend_yield_pct": result["dividend_yield_pct"],
        "aggregate_earnings_yield": result["aggregate_earnings_yield"],
        "aggregate_book_yield": result["aggregate_book_yield"],
        "aggregate_dividend_yield": result["aggregate_dividend_yield"],
    }


def _relative_error_pct(actual: float, target: float, name: str) -> float:
    actual = _finite_number(actual, name)
    target = _finite_number(target, f"target_{name}")
    if target == 0:
        raise DevelopmentReconstructionError(f"target_{name} cannot be zero for relative error")
    return abs(actual / target - 1.0) * 100.0


def compare_to_visible_development_target(reconstructed: dict, target: dict) -> dict:
    """Apply only the preregistered six-month reproduction thresholds."""
    month = assert_development_month(reconstructed.get("month"))
    if str(target.get("month")) != month:
        raise DevelopmentReconstructionError("target month mismatch")
    if reconstructed.get("status") != "reconstructed":
        raise DevelopmentReconstructionError("month is not reconstructed")
    if reconstructed.get("pe") is None or reconstructed.get("pb") is None:
        raise DevelopmentReconstructionError("development comparison requires defined P/E and P/B")

    pe_err = _relative_error_pct(reconstructed["pe"], target.get("pe"), "pe")
    pb_err = _relative_error_pct(reconstructed["pb"], target.get("pb"), "pb")
    dy_actual = _finite_number(reconstructed.get("dividend_yield_pct"), "dividend_yield_pct")
    dy_target = _finite_number(target.get("dividend_yield_pct"), "target_dividend_yield_pct")
    dy_err = abs(dy_actual - dy_target)

    return {
        "month": month,
        "pe_relative_error_pct": pe_err,
        "pb_relative_error_pct": pb_err,
        "dividend_yield_abs_error_pp": dy_err,
        "per_month_pass": (
            pe_err <= float(GATE["per_month_pe_relative_error_max_pct"])
            and pb_err <= float(GATE["per_month_pb_relative_error_max_pct"])
            and dy_err <= float(GATE["per_month_dividend_yield_abs_error_max_pp"])
        ),
    }


def evaluate_six_month_development(reconstructed_months: Iterable[dict], targets: Iterable[dict]) -> dict:
    """Evaluate the complete visible development window; no partial pass exists."""
    recs = {r["month"]: r for r in reconstructed_months}
    tgts = {t["month"]: t for t in targets}
    if tuple(sorted(recs)) != DEVELOPMENT_MONTHS:
        raise DevelopmentReconstructionError("reconstructed set must be exactly the six frozen development months")
    if tuple(sorted(tgts)) != DEVELOPMENT_MONTHS:
        raise DevelopmentReconstructionError("target set must be exactly the six frozen development months")

    comparisons = [compare_to_visible_development_target(recs[m], tgts[m]) for m in DEVELOPMENT_MONTHS]
    pe = sorted(x["pe_relative_error_pct"] for x in comparisons)
    pb = sorted(x["pb_relative_error_pct"] for x in comparisons)
    dy = sorted(x["dividend_yield_abs_error_pp"] for x in comparisons)
    median = lambda xs: (xs[2] + xs[3]) / 2.0
    med_pe, med_pb, med_dy = median(pe), median(pb), median(dy)
    all_months_pass = all(x["per_month_pass"] for x in comparisons)
    median_pass = (
        med_pe <= float(GATE["median_pe_relative_error_max_pct"])
        and med_pb <= float(GATE["median_pb_relative_error_max_pct"])
        and med_dy <= float(GATE["median_dividend_yield_abs_error_max_pp"])
    )
    return {
        "policy_id": POLICY["policy_id"],
        "research_only": True,
        "live_authority": "none",
        "holdout_target_fetch_count": 0,
        "development_months": list(DEVELOPMENT_MONTHS),
        "comparisons": comparisons,
        "median_pe_relative_error_pct": med_pe,
        "median_pb_relative_error_pct": med_pb,
        "median_dividend_yield_abs_error_pp": med_dy,
        "all_months_pass": all_months_pass,
        "median_pass": median_pass,
        "development_gate_pass": all_months_pass and median_pass,
        "promotion_effect": "none",
    }


def validate_engine_contract() -> dict:
    if DEVELOPMENT_MONTHS != ("2023-09", "2023-10", "2023-11", "2023-12", "2024-01", "2024-02"):
        raise DevelopmentReconstructionError("development window changed")
    if POLICY.get("holdout_target_fetch_count") != 0:
        raise DevelopmentReconstructionError("policy reports holdout target access")
    if POLICY.get("live_authority") != "none":
        raise DevelopmentReconstructionError("development policy acquired live authority")
    return {
        "engine": "development-numerical-reconstruction-v1",
        "development_months": list(DEVELOPMENT_MONTHS),
        "holdout_start": HOLDOUT_START,
        "holdout_target_fetch_count": 0,
        "live_authority": "none",
    }


if __name__ == "__main__":
    print(json.dumps(validate_engine_contract(), indent=2))
