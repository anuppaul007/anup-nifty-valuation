#!/usr/bin/env python3
"""Fail-closed accounting semantic primitives for the blinded development pilot.

Research only. This module freezes context, candidate-fact and quarter-chain
semantics before any NIFTY development ratio is reconstructed. It does not
fetch valuation targets and contains no index P/E, P/B or dividend-yield
aggregation formula.
"""
from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "development_accounting_semantics_policy_v1.json"
POLICY = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

CURRENT_CONTEXT = POLICY["xbrl_column_semantics"]["legacy_current_period_context"]
YTD_CONTEXT = POLICY["xbrl_column_semantics"]["legacy_ytd_current_period_context"]


class SemanticError(ValueError):
    """Raised when a filing cannot be interpreted without an accounting guess."""


def context_role(context_ref: str | None) -> str:
    """Map only preregistered legacy column IDs; unknown contexts fail closed."""
    if context_ref == CURRENT_CONTEXT:
        return "current_period"
    if context_ref == YTD_CONTEXT:
        return "year_to_date"
    raise SemanticError(f"unknown legacy XBRL context: {context_ref!r}")


def normalise_numeric(value: object, *, scale: object = None, sign: object = None) -> float:
    """Normalise one XBRL numeric fact without interpreting decimals as scale."""
    text = str(value).strip().replace(",", "")
    paren_negative = text.startswith("(") and text.endswith(")")
    if paren_negative:
        text = text[1:-1].strip()
    if text in {"", "-", "—", "–"}:
        raise SemanticError("blank/non-numeric accounting fact")
    try:
        number = float(text)
    except Exception as exc:
        raise SemanticError(f"non-numeric accounting fact: {value!r}") from exc

    explicit_negative = str(sign or "").strip() == "-"
    if paren_negative and number < 0:
        raise SemanticError("negative sign encoded twice")
    if explicit_negative and number < 0:
        raise SemanticError("negative sign encoded twice")
    if paren_negative or explicit_negative:
        number = -number

    if scale not in (None, ""):
        try:
            power = int(str(scale))
        except Exception as exc:
            raise SemanticError(f"invalid XBRL scale: {scale!r}") from exc
        number *= 10 ** power
    return number


def _dimensions(fact: dict) -> list:
    context = fact.get("context") or {}
    dims = context.get("dimensions") or []
    return list(dims)


def select_entity_fact(
    facts: Iterable[dict],
    *,
    local_name: str,
    context_ref: str = CURRENT_CONTEXT,
) -> dict:
    """Select one total-entity fact for an exact concept/context or reject ambiguity.

    Dimensional/segment facts are not eligible for company-level earnings or
    net worth. Duplicate eligible facts are accepted only when their normalised
    numeric values are exactly equal.
    """
    context_role(context_ref)  # fail if caller attempts an unregistered context
    eligible = [
        f for f in facts
        if f.get("local_name") == local_name
        and f.get("context_ref") == context_ref
        and not _dimensions(f)
    ]
    if not eligible:
        raise SemanticError(f"missing {local_name} in {context_ref}")

    values = [
        normalise_numeric(f.get("value"), scale=f.get("scale"), sign=f.get("sign"))
        for f in eligible
    ]
    first = values[0]
    if any(v != first for v in values[1:]):
        raise SemanticError(f"unequal duplicate facts for {local_name} in {context_ref}: {values}")
    chosen = dict(eligible[0])
    chosen["normalised_value"] = first
    chosen["semantic_role"] = context_role(context_ref)
    chosen["duplicate_count"] = len(eligible)
    return chosen


def _as_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except Exception as exc:
        raise SemanticError(f"invalid period end: {value!r}") from exc


def _next_quarter_end(d: date) -> date:
    sequence = {
        (3, 31): date(d.year, 6, 30),
        (6, 30): date(d.year, 9, 30),
        (9, 30): date(d.year, 12, 31),
        (12, 31): date(d.year + 1, 3, 31),
    }
    try:
        return sequence[(d.month, d.day)]
    except KeyError as exc:
        raise SemanticError(f"not a calendar quarter end: {d.isoformat()}") from exc


def validate_four_quarter_chain(period_ends: Iterable[str | date | datetime]) -> list[date]:
    ends = sorted(_as_date(x) for x in period_ends)
    if len(ends) != 4 or len(set(ends)) != 4:
        raise SemanticError(f"TTM requires four distinct quarter ends, got {ends}")
    for left, right in zip(ends, ends[1:]):
        if _next_quarter_end(left) != right:
            raise SemanticError(f"non-consecutive TTM quarter chain: {ends}")
    return ends


def ttm_from_current_quarters(quarters: Iterable[dict]) -> float:
    """Sum four signed quarter-only facts; YTD facts are explicitly inadmissible."""
    rows = list(quarters)
    if len(rows) != 4:
        raise SemanticError("TTM requires exactly four quarter facts")
    validate_four_quarter_chain(r["period_end"] for r in rows)
    for row in rows:
        if row.get("context_ref") != CURRENT_CONTEXT:
            role = context_role(row.get("context_ref"))
            raise SemanticError(f"TTM cannot sum {role} facts")
    return sum(
        normalise_numeric(r.get("value"), scale=r.get("scale"), sign=r.get("sign"))
        for r in rows
    )


def validate_policy() -> dict:
    assert POLICY["policy_id"] == "development-accounting-semantics-v1"
    assert POLICY["research_only"] is True
    assert POLICY["live_authority"] == "none"
    assert POLICY["holdout_target_fetch_count"] == 0
    assert POLICY["ratios_computed"] is False
    assert CURRENT_CONTEXT == "OneD"
    assert YTD_CONTEXT == "FourD"

    development = POLICY["scope"]["development_months"]
    if development != ["2023-09", "2023-10", "2023-11", "2023-12", "2024-01", "2024-02"]:
        raise SemanticError("development window changed")

    ids = []
    for family in ("INDAS", "BANKING"):
        for candidate in POLICY["profit_candidates"][family]:
            if candidate["context_ref"] != CURRENT_CONTEXT:
                raise SemanticError(f"profit candidate is not quarter-only: {candidate}")
            ids.append(candidate["candidate_id"])
    if len(ids) != len(set(ids)):
        raise SemanticError("duplicate candidate IDs")

    return {
        "policy_id": POLICY["policy_id"],
        "research_only": True,
        "live_authority": "none",
        "development_months": development,
        "current_period_context": CURRENT_CONTEXT,
        "ytd_context": YTD_CONTEXT,
        "profit_candidate_ids": ids,
        "holdout_target_fetch_count": 0,
        "ratios_computed": False,
    }


if __name__ == "__main__":
    print(json.dumps(validate_policy(), indent=2))
