import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "development_difficult_cases_policy_v1.json").read_text(encoding="utf-8"))


class DifficultCaseGovernanceTests(unittest.TestCase):
    def test_zero_live_authority_and_holdout_sealed(self):
        self.assertTrue(POLICY["research_only"])
        self.assertEqual(POLICY["live_authority"], "none")
        self.assertFalse(POLICY["live_model_changed"])
        self.assertFalse(POLICY["live_allocation_changed"])
        self.assertEqual(POLICY["holdout_target_fetch_count"], 0)
        self.assertEqual(POLICY["sealed_holdout"], "2024-03 through 2026-08")
        self.assertFalse(POLICY["milestone_gate"]["holdout_opening_allowed"])

    def test_development_window_is_frozen(self):
        self.assertEqual(
            POLICY["development_window"],
            ["2023-09", "2023-10", "2023-11", "2023-12", "2024-01", "2024-02"],
        )
        self.assertTrue(POLICY["milestone_gate"]["all_50_constituents_required_each_development_month"])
        self.assertTrue(POLICY["milestone_gate"]["development_ratio_evaluation_allowed_only_after_all_cases_resolved"])

    def test_no_tuning_or_gap_filling_rules_are_locked(self):
        rules = POLICY["global_rules"]
        for key in ("no_outcome_driven_selection", "no_imputation", "no_index_renormalisation", "no_loss_maker_exclusion", "point_in_time_only"):
            self.assertTrue(rules[key], key)
        self.assertEqual(rules["secondary_finance_sites"], "prohibited_as_source_of_record")
        self.assertEqual(
            rules["source_priority"],
            ["official_NSE_structured", "official_NSE_archive_or_announcement", "preregistered_first_party_issuer_exception"],
        )

    def test_exact_difficult_case_registry_is_locked(self):
        cases = {case["case_id"]: case for case in POLICY["cases"]}
        self.assertEqual(
            set(cases),
            {
                "NESTLEIND_TRANSITION_YEAR",
                "INDUSINDBK_ARCHIVE_XML",
                "BANK_ANNUAL_NET_WORTH",
                "NBFC_ANNUAL_NET_WORTH",
                "LIFE_INSURANCE_ACCOUNTING",
                "ICICIBANK_SHARE_COUNT",
            },
        )
        self.assertEqual(cases["NESTLEIND_TRANSITION_YEAR"]["status"], "blocked_retrieval")
        self.assertEqual(cases["INDUSINDBK_ARCHIVE_XML"]["status"], "blocked_archive")
        self.assertEqual(cases["BANK_ANNUAL_NET_WORTH"]["status"], "semantic_unresolved")
        self.assertEqual(cases["NBFC_ANNUAL_NET_WORTH"]["status"], "semantic_unresolved")
        self.assertEqual(cases["LIFE_INSURANCE_ACCOUNTING"]["status"], "separate_template_required")
        self.assertEqual(cases["ICICIBANK_SHARE_COUNT"]["status"], "capital_continuity_unresolved")
        for case in cases.values():
            self.assertTrue(case.get("completion_gate"))

    def test_resolution_cannot_be_declared_by_numerical_fit(self):
        rules = POLICY["global_rules"]
        joined = " ".join(rules["resolution_requires"]).lower()
        self.assertIn("source identity", joined)
        self.assertIn("accounting concept", joined)
        self.assertIn("corporate-action", joined)
        self.assertEqual(POLICY["milestone_gate"]["required_case_status"], "resolved_or_explicitly_proven_unreconstructable")


if __name__ == "__main__":
    unittest.main()
