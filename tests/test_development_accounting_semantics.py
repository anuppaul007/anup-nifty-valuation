from pathlib import Path
import importlib.util
import json
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("sem", SCRIPTS / "development_accounting_semantics.py")
sem = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sem)


def fact(name, ctx, value, *, scale=None, sign=None, dimensions=None):
    return {
        "local_name": name,
        "context_ref": ctx,
        "value": value,
        "scale": scale,
        "sign": sign,
        "context": {"dimensions": dimensions or []},
    }


def test_context_semantics_are_frozen_and_unknown_fails():
    assert sem.context_role("OneD") == "current_period"
    assert sem.context_role("FourD") == "year_to_date"
    with pytest.raises(sem.SemanticError):
        sem.context_role("TwoD")


def test_current_period_fact_rejects_segment_dimensions():
    rows = [
        fact("ProfitLossForPeriod", "OneD", "100", dimensions=[{"dimension": "SegmentAxis", "value": "A"}]),
        fact("ProfitLossForPeriod", "OneD", "80"),
    ]
    chosen = sem.select_entity_fact(rows, local_name="ProfitLossForPeriod")
    assert chosen["normalised_value"] == 80


def test_unequal_duplicates_fail_but_equal_duplicates_are_deterministic():
    with pytest.raises(sem.SemanticError):
        sem.select_entity_fact(
            [fact("ProfitLossForPeriod", "OneD", "10"), fact("ProfitLossForPeriod", "OneD", "11")],
            local_name="ProfitLossForPeriod",
        )
    chosen = sem.select_entity_fact(
        [fact("ProfitLossForPeriod", "OneD", "10"), fact("ProfitLossForPeriod", "OneD", "10")],
        local_name="ProfitLossForPeriod",
    )
    assert chosen["normalised_value"] == 10
    assert chosen["duplicate_count"] == 2


def test_signed_and_scaled_values_preserve_losses():
    assert sem.normalise_numeric("(12.5)") == -12.5
    assert sem.normalise_numeric("12.5", sign="-") == -12.5
    assert sem.normalise_numeric("12.5", scale="3") == 12500
    with pytest.raises(sem.SemanticError):
        sem.normalise_numeric("-12.5", sign="-")


def test_ttm_requires_four_consecutive_current_period_quarters():
    rows = [
        {"period_end": "2022-12-31", "context_ref": "OneD", "value": "10"},
        {"period_end": "2023-03-31", "context_ref": "OneD", "value": "-2"},
        {"period_end": "2023-06-30", "context_ref": "OneD", "value": "5"},
        {"period_end": "2023-09-30", "context_ref": "OneD", "value": "7"},
    ]
    assert sem.ttm_from_current_quarters(rows) == 20

    broken = [dict(r) for r in rows]
    broken[2]["period_end"] = "2023-09-30"
    with pytest.raises(sem.SemanticError):
        sem.ttm_from_current_quarters(broken)


def test_ttm_rejects_ytd_even_when_dates_look_valid():
    rows = [
        {"period_end": "2022-12-31", "context_ref": "OneD", "value": "10"},
        {"period_end": "2023-03-31", "context_ref": "OneD", "value": "20"},
        {"period_end": "2023-06-30", "context_ref": "FourD", "value": "30"},
        {"period_end": "2023-09-30", "context_ref": "OneD", "value": "40"},
    ]
    with pytest.raises(sem.SemanticError, match="year_to_date"):
        sem.ttm_from_current_quarters(rows)


def test_policy_contains_competing_candidates_before_target_fit():
    p = sem.POLICY
    assert [x["candidate_id"] for x in p["profit_candidates"]["INDAS"]] == [
        "indas_profit_for_period",
        "indas_parent_attributable_profit",
    ]
    assert [x["candidate_id"] for x in p["profit_candidates"]["BANKING"]] == [
        "bank_profit_for_period",
        "bank_post_tax_parent_adjusted_profit",
    ]
    assert p["annual_net_worth_candidates"]["BANKING"][0]["status"] == "candidate_not_yet_authorized"


def test_development_error_hurdle_reuses_existing_preregistered_limits():
    prior = json.loads((ROOT / "recent_reconstruction_policy_v1.json").read_text(encoding="utf-8"))
    old = prior["predeclared_holdout_tolerance"]
    gate = sem.POLICY["development_candidate_reproduction_gate"]
    assert gate["months_required"] == 6
    assert gate["full_constituent_completeness_required"] is True
    for key in (
        "per_month_pe_relative_error_max_pct",
        "per_month_pb_relative_error_max_pct",
        "per_month_dividend_yield_abs_error_max_pp",
        "median_pe_relative_error_max_pct",
        "median_pb_relative_error_max_pct",
        "median_dividend_yield_abs_error_max_pp",
    ):
        assert gate[key] == old[key]


def test_module_has_no_index_ratio_or_holdout_fetch_authority():
    text = (SCRIPTS / "development_accounting_semantics.py").read_text(encoding="utf-8")
    assert "aggregate_from_point_in_time_inputs" not in text
    assert "niftyindices.com/Index_Dashboard" not in text
    result = sem.validate_policy()
    assert result["holdout_target_fetch_count"] == 0
    assert result["ratios_computed"] is False
