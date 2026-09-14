from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
P = json.loads((ROOT / "institutional_validation_protocol_v1.json").read_text(encoding="utf-8"))
V = json.loads((ROOT / "validation_policy.json").read_text(encoding="utf-8"))
R = json.loads((ROOT / "historical_regime_policy_v1.json").read_text(encoding="utf-8"))
D = json.loads((ROOT / "point_in_time_panel_spec_v1.json").read_text(encoding="utf-8"))
I = json.loads((ROOT / "implementation_cost_tax_policy_v1.json").read_text(encoding="utf-8"))


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


def test_legacy_validation_policy_is_harmonized():
    assert V["protocol_version"] == "2026-09-14-v4"
    assert V["controlling_institutional_protocol"] == "institutional_validation_protocol_v1.json"
    assert "Exposure-matched" in V["primary_metric"]
    assert "Maximum daily drawdown" in V["primary_risk_metric"]
    assert V["macro_governance"]["live_budget_pp"] == 0
    assert V["prospective_evidence_purpose"]["minimum_completed_months_before_promotion_review"] == 60
    assert "confirmation-eligible only" in V["promotion_rule"]
    assert V["automatic_parameter_changes"] is False


def test_current_definition_and_long_vintage_claims_are_separate():
    assert R["policy_id"] == "historical-methodology-regime-policy-v1"
    assert R["research_only"] is True
    assert R["live_authority"] == "none"
    assert R["current_definition_track"]["legacy_ratio_backfill_allowed"] is False
    assert R["current_definition_track"]["promotion_effect"] == "data_lineage_confidence_only"
    assert R["long_vintage_track"]["every_row_requires_methodology_regime"] is True
    assert R["long_vintage_track"]["hindsight_rewrite_to_current_definition_allowed"] is False
    assert R["long_vintage_track"]["ex_post_level_stitching_allowed"] is False
    assert R["long_vintage_track"]["regime_specific_results_required"] is True
    assert "validated timing residual" in R["claim_boundary"]["neither_alone_may_support"]
    assert R["automatic_parameter_changes"] is False


def test_point_in_time_panel_contract_fails_closed():
    assert D["spec_id"] == "point-in-time-panel-v1"
    assert D["research_only"] is True
    assert D["live_authority"] == "none"
    assert D["availability_policy"]["after_cutoff_use_allowed"] is False
    assert D["availability_policy"]["future_revision_backfill_allowed"] is False
    assert D["source_integrity"]["raw_bytes_hash_required"] is True
    assert D["source_integrity"]["secondary_source_fill_allowed"] is False
    assert D["selection_policy"]["missing_value_imputation_allowed"] is False
    assert D["selection_policy"]["neutral_fill_allowed"] is False
    assert D["selection_policy"]["ambiguous_fact_eligible"] is False
    assert D["methodology_regimes"]["hindsight_rewrite_to_later_definition_allowed"] is False
    assert D["methodology_regimes"]["ex_post_level_stitching_allowed"] is False
    assert D["certification_gates"]["selected_row_after_decision_cutoff_allowed"] is False
    assert D["certification_gates"]["selected_row_without_source_hash_allowed"] is False
    assert D["separation_of_concerns"]["join_rule"].startswith("Signal and outcome panels may be joined")
    assert D["promotion_effect"].startswith("none")
    assert D["automatic_parameter_changes"] is False


def test_cost_tax_policy_is_path_aware_and_no_double_counting():
    assert I["policy_id"] == "implementation-cost-tax-policy-v1"
    assert I["research_only"] is True
    assert I["live_authority"] == "none"
    assert I["primary_trading_friction"]["one_way_bps_on_traded_notional"] == 15
    assert I["primary_trading_friction"]["sensitivities_bps"] == [10, 25]
    assert I["embedded_cost_rule"]["double_counting_prohibited"] is True
    assert I["tax_profile_rule"]["universal_india_tax_assumption_prohibited"] is True
    assert I["tax_profile_rule"]["lot_aware_realization_required"] is True
    assert I["claim_gates"]["taxable_implementation_claim_requires_after_tax_residual_cagr_pp_per_year_min"] == 0.8
    assert I["claim_gates"]["incomplete_tax_engine_may_support_promotion"] is False
    assert I["claim_gates"]["favorable_tax_profile_selection_after_outcomes_allowed"] is False
    assert I["debt_vehicle_rule"]["selection_based_on_backtest_return_allowed"] is False
    assert I["automatic_parameter_changes"] is False
