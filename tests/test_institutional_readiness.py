import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import institutional_readiness as ir


class InstitutionalReadinessTests(unittest.TestCase):
    def setUp(self):
        self.policy = ir.load_json(ROOT / "institutional_readiness_policy_v1.json")
        self.robust = ir.load_json(ROOT / "data" / "robust_evaluation_summary.json")

    def passing_robust(self):
        robust = copy.deepcopy(self.robust)
        for key in self.policy["controlling_evidence"]["required_gate_keys"]:
            robust["gate_matrix"][key] = True
        robust["decision"] = self.policy["controlling_evidence"]["eligible_promotion_decision"]
        return robust

    def passing_policy(self):
        policy = copy.deepcopy(self.policy)
        for dimension in policy["dimensions"]:
            dimension["score"] = 100.0
        policy["material_model_risk_clearance"]["cleared"] = True
        policy["material_model_risk_clearance"]["reason"] = "Synthetic unit-test clearance only."
        return policy

    def test_current_evidence_reproduces_frozen_score_and_blocks_cio(self):
        status = ir.compute_status(self.policy, self.robust)
        self.assertEqual(status["score"]["exact"], 51.75)
        self.assertEqual(status["score"]["rounded_1dp"], 51.8)
        self.assertFalse(status["score"]["threshold_pass"])
        self.assertFalse(status["critical_dimensions"]["threshold_pass"])
        self.assertFalse(status["controlling_gates"]["all_controlling_gates_pass"])
        self.assertFalse(status["material_model_risk_clearance"]["cleared"])
        self.assertFalse(status["eligible_for_cio_framework"])
        self.assertEqual(status["decision"], "NOT_CIO_ELIGIBLE")

    def test_high_weighted_score_cannot_average_away_failed_gates(self):
        policy = self.passing_policy()
        policy["material_model_risk_clearance"]["cleared"] = True
        status = ir.compute_status(policy, self.robust)
        self.assertEqual(status["score"]["exact"], 100.0)
        self.assertTrue(status["critical_dimensions"]["threshold_pass"])
        self.assertFalse(status["controlling_gates"]["all_controlling_gates_pass"])
        self.assertFalse(status["eligible_for_cio_framework"])

    def test_critical_floor_blocks_even_when_gates_pass(self):
        policy = self.passing_policy()
        critical = next(d for d in policy["dimensions"] if d["critical"])
        critical["score"] = 79.0
        status = ir.compute_status(policy, self.passing_robust())
        self.assertTrue(status["score"]["threshold_pass"])
        self.assertFalse(status["critical_dimensions"]["threshold_pass"])
        self.assertTrue(status["controlling_gates"]["all_controlling_gates_pass"])
        self.assertFalse(status["eligible_for_cio_framework"])

    def test_model_risk_clearance_is_independent_required_gate(self):
        policy = self.passing_policy()
        policy["material_model_risk_clearance"]["cleared"] = False
        policy["material_model_risk_clearance"]["reason"] = "Synthetic unresolved defect."
        status = ir.compute_status(policy, self.passing_robust())
        self.assertTrue(status["score"]["threshold_pass"])
        self.assertTrue(status["critical_dimensions"]["threshold_pass"])
        self.assertTrue(status["controlling_gates"]["all_controlling_gates_pass"])
        self.assertFalse(status["eligible_for_cio_framework"])

    def test_all_frozen_admission_conditions_are_jointly_sufficient(self):
        status = ir.compute_status(self.passing_policy(), self.passing_robust())
        self.assertTrue(status["score"]["threshold_pass"])
        self.assertTrue(status["critical_dimensions"]["threshold_pass"])
        self.assertTrue(status["controlling_gates"]["all_controlling_gates_pass"])
        self.assertTrue(status["material_model_risk_clearance"]["cleared"])
        self.assertTrue(status["eligible_for_cio_framework"])
        self.assertEqual(status["decision"], "ELIGIBLE_TO_ENTER_CIO_FRAMEWORK")

    def test_missing_or_nonboolean_controlling_gate_fails_closed(self):
        key = self.policy["controlling_evidence"]["required_gate_keys"][0]
        missing = copy.deepcopy(self.robust)
        del missing["gate_matrix"][key]
        with self.assertRaises(ir.ReadinessError):
            ir.compute_status(self.policy, missing)

        malformed = copy.deepcopy(self.robust)
        malformed["gate_matrix"][key] = 1
        with self.assertRaises(ir.ReadinessError):
            ir.compute_status(self.policy, malformed)

    def test_weights_and_thresholds_are_frozen(self):
        bad_weight = copy.deepcopy(self.policy)
        bad_weight["dimensions"][0]["weight_pct"] += 1
        with self.assertRaises(ir.ReadinessError):
            ir.validate_policy(bad_weight)

        bad_threshold = copy.deepcopy(self.policy)
        bad_threshold["admission_rule"]["overall_score_min"] = 89.0
        with self.assertRaises(ir.ReadinessError):
            ir.validate_policy(bad_threshold)

    def test_committed_status_matches_recomputation(self):
        expected = ir.compute_status(self.policy, self.robust)
        committed = json.loads((ROOT / "data" / "institutional_readiness.json").read_text(encoding="utf-8"))
        self.assertEqual(committed, expected)


if __name__ == "__main__":
    unittest.main()
