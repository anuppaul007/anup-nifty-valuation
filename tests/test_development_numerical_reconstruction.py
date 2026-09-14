import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import development_numerical_reconstruction as dnr


class DevelopmentNumericalReconstructionTests(unittest.TestCase):
    def make_rows(self):
        rows = []
        for i in range(50):
            rows.append({
                "symbol": f"C{i:02d}",
                "weight": 2.0,
                "market_cap": 1000.0,
                "ttm_earnings": 50.0 if i != 0 else -25.0,
                "book_value": 250.0,
                "rolling_12m_dividends": 10.0,
                "filing_ok": True,
                "dividend_history_ok": True,
                "market_cap_basis_ok": True,
                "corporate_action_continuity_ok": True,
            })
        return rows

    def test_engine_contract_keeps_holdout_sealed(self):
        out = dnr.validate_engine_contract()
        self.assertEqual(out["holdout_target_fetch_count"], 0)
        self.assertEqual(out["live_authority"], "none")
        self.assertEqual(len(out["development_months"]), 6)
        with self.assertRaises(dnr.DevelopmentReconstructionError):
            dnr.assert_development_month("2024-03")
        with self.assertRaises(dnr.DevelopmentReconstructionError):
            dnr.assert_development_month("2026-08")

    def test_reconstruct_requires_complete_50_constituent_panel(self):
        rows = self.make_rows()
        out = dnr.reconstruct_month("2023-09", rows)
        self.assertEqual(out["constituents"], 50)
        self.assertTrue(out["pe_publishable"])
        self.assertGreater(out["pe"], 0)
        with self.assertRaises(dnr.DevelopmentReconstructionError):
            dnr.reconstruct_month("2023-09", rows[:-1])

    def test_signed_loss_maker_is_preserved(self):
        rows = self.make_rows()
        with_loss = dnr.reconstruct_month("2023-09", rows)
        rows[0]["ttm_earnings"] = 50.0
        without_loss = dnr.reconstruct_month("2023-09", rows)
        self.assertGreater(with_loss["pe"], without_loss["pe"])

    def test_duplicate_symbols_fail_closed(self):
        rows = self.make_rows()
        rows[1]["symbol"] = rows[0]["symbol"]
        with self.assertRaises(dnr.DevelopmentReconstructionError):
            dnr.reconstruct_month("2023-09", rows)

    def test_visible_target_thresholds_are_exactly_frozen_policy(self):
        rec = {
            "month": "2023-09", "status": "reconstructed",
            "pe": 20.0, "pb": 4.0, "dividend_yield_pct": 1.20,
        }
        target = {"month": "2023-09", "pe": 20.2, "pb": 4.02, "dividend_yield_pct": 1.18}
        out = dnr.compare_to_visible_development_target(rec, target)
        self.assertTrue(out["per_month_pass"])
        self.assertLessEqual(out["pe_relative_error_pct"], 2.0)
        self.assertLessEqual(out["pb_relative_error_pct"], 2.0)
        self.assertLessEqual(out["dividend_yield_abs_error_pp"], 0.05)

    def test_six_month_gate_rejects_partial_or_holdout_target_sets(self):
        recs, tgts = [], []
        for m in dnr.DEVELOPMENT_MONTHS:
            recs.append({"month": m, "status": "reconstructed", "pe": 20.0, "pb": 4.0, "dividend_yield_pct": 1.2})
            tgts.append({"month": m, "pe": 20.1, "pb": 4.01, "dividend_yield_pct": 1.19})
        out = dnr.evaluate_six_month_development(recs, tgts)
        self.assertTrue(out["development_gate_pass"])
        self.assertEqual(out["holdout_target_fetch_count"], 0)
        self.assertEqual(out["promotion_effect"], "none")

        with self.assertRaises(dnr.DevelopmentReconstructionError):
            dnr.evaluate_six_month_development(recs[:-1], tgts[:-1])

        bad = list(tgts)
        bad[-1] = {"month": "2024-03", "pe": 20.1, "pb": 4.01, "dividend_yield_pct": 1.19}
        with self.assertRaises(dnr.DevelopmentReconstructionError):
            dnr.evaluate_six_month_development(recs, bad)


if __name__ == "__main__":
    unittest.main()
