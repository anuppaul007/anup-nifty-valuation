import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import development_manual_evidence as dme


class DevelopmentManualEvidenceTests(unittest.TestCase):
    def test_frozen_nestle_evidence_reconciles(self):
        out = dme.validate_nestle_evidence()
        self.assertEqual(out["quarters"], 6)
        self.assertEqual(out["development_ttm_months"], 6)
        self.assertTrue(out["share_count_rounding_reconciled"])
        self.assertTrue(out["share_split_reconciled"])
        self.assertTrue(out["annual_book_reconciled"])
        self.assertFalse(out["dividend_evidence_complete"])
        self.assertFalse(out["machine_reproducible_source_retrieval"])
        self.assertEqual(out["holdout_target_fetch_count"], 0)
        self.assertEqual(out["live_authority"], "none")

    def test_rounded_capital_allows_exact_disclosed_share_count(self):
        self.assertTrue(dme._share_count_within_reported_capital_rounding(
            paid_up_mn=964.2, face_value=10.0, disclosed_shares=96_415_716
        ))
        self.assertTrue(dme._share_count_within_reported_capital_rounding(
            paid_up_mn=964.2, face_value=1.0, disclosed_shares=964_157_160
        ))
        self.assertFalse(dme._share_count_within_reported_capital_rounding(
            paid_up_mn=964.2, face_value=10.0, disclosed_shares=96_300_000
        ))

    def test_manual_bridge_cannot_claim_machine_reproducibility(self):
        src = json.loads(dme.NESTLE_PATH.read_text())
        src["machine_reproducible_source_retrieval"] = True
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "evidence.json"
            p.write_text(json.dumps(src))
            with self.assertRaises(dme.ManualEvidenceError):
                dme.validate_nestle_evidence(p)

    def test_ttm_tampering_fails_closed(self):
        src = json.loads(dme.NESTLE_PATH.read_text())
        src["ttm_profit_by_development_month"]["2023-09"] += 1.0
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "evidence.json"
            p.write_text(json.dumps(src))
            with self.assertRaises(dme.ManualEvidenceError):
                dme.validate_nestle_evidence(p)

    def test_split_tampering_fails_closed(self):
        src = json.loads(dme.NESTLE_PATH.read_text())
        src["corporate_actions"][0]["new_shares"] -= 1
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "evidence.json"
            p.write_text(json.dumps(src))
            with self.assertRaises(dme.ManualEvidenceError):
                dme.validate_nestle_evidence(p)

    def test_material_share_count_tampering_fails_closed(self):
        src = json.loads(dme.NESTLE_PATH.read_text())
        src["quarter_facts"][0]["shares_outstanding"] -= 100_000
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "evidence.json"
            p.write_text(json.dumps(src))
            with self.assertRaises(dme.ManualEvidenceError):
                dme.validate_nestle_evidence(p)


if __name__ == "__main__":
    unittest.main()
