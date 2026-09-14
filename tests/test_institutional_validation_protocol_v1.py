from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
P = json.loads((ROOT / "institutional_validation_protocol_v1.json").read_text(encoding="utf-8"))


def test_protocol_has_zero_live_authority():
    assert P["protocol_id"] == "institutional-validation-protocol-v1"
    assert P["research_only"] is True
    assert P["live_authority"] == "none"
    assert P["live_model_changed"] is False
    assert P["live_allocation_changed"] is False
    assert P["automatic_parameter_changes"] is False


def test_sample_and_economic_hurdles_are_frozen():
    assert P["sample"]["target_completed_months"] == 180
    assert P["sample"]["minimum_completed_months_for_validation_language_review"] == 120
    assert P["primary_effect"]["economic_materiality_min_pp_per_year"] == 0.8
    assert P["primary_effect"]["familywise_one_sided_alpha_max"] == 0.05
    assert P["primary_effect"]["paired_block_bootstrap_95_lower_bound_must_exceed_zero"] is True


def test_implementation_assumptions_are_predeclared():
    assert P["costs"]["primary_one_way_bps_on_traded_notional"] == 15
    assert P["costs"]["sensitivity_one_way_bps"] == [10, 25]
    assert P["outcome_matrix"]["rebalance_band_sensitivities_pp"] == [0, 5, 10]
    assert P["tax"]["universal_india_after_tax_return_prohibited"] is True
    assert P["tax"]["pre_tax_net_of_cost_results_required"] is True


def test_trial_family_and_confirmation_cannot_auto_promote():
    assert P["trial_family"]["maximum_preregistered_variants_first_certified_panel_family"] == 6
    assert P["trial_family"]["comparable_existing_lineage_consumes_family_count"] is True
    assert P["historical_pass_effect"] == "confirmation_eligible_only"
    assert P["prospective_confirmation"]["minimum_completed_months_before_promotion_review"] == 60
    assert P["independent_review"]["another_ai_or_author_duplicate_is_not_independent"] is True


def test_overlays_remain_separate():
    assert P["overlays"]["macro_live_authority_pp"] == 0
    assert "insurance" in P["overlays"]["trend"].lower()
    assert "separate challenger" in P["overlays"]["earnings"].lower()


def test_dsr_pbo_are_not_unconditional_hard_gates():
    assert P["dsr_pbo"]["mandatory_diagnostics_when_estimable"] is True
    assert P["dsr_pbo"]["hard_gate_only_after_adequacy_documented"] is True
    assert P["dsr_pbo"]["not_adequate_label"] == "not_decision_grade"


def test_claim_language_is_conservative():
    assert P["current_state"]["historical_timing_promotion_eligible"] is False
    assert P["current_state"]["v3_13_changed_by_protocol"] is False
    assert "independent review" in P["claims_language"]["validated_timing_or_institutional_validation"].lower()
    assert "confirmation" in P["claims_language"]["validated_timing_or_institutional_validation"].lower()
