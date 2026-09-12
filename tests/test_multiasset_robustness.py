import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import multiasset_robustness as mr


class MultiAssetRobustnessTests(unittest.TestCase):
    def test_proportional_funding_preserves_equity_debt_ratio(self):
        w = mr.fund_metals(0.80, 0.20, 0.12, 0.04, 'proportional')
        self.assertAlmostEqual(sum(w.values()), 1.0)
        self.assertAlmostEqual(w['equity'] / w['debt'], 4.0)

    def test_equity_first_funds_metals_from_equity(self):
        w = mr.fund_metals(0.80, 0.20, 0.12, 0.04, 'equity_first')
        self.assertAlmostEqual(w['equity'], 0.64)
        self.assertAlmostEqual(w['debt'], 0.20)
        self.assertAlmostEqual(sum(w.values()), 1.0)

    def test_debt_first_spills_into_equity_if_needed(self):
        w = mr.fund_metals(0.90, 0.10, 0.12, 0.04, 'debt_first')
        self.assertAlmostEqual(w['debt'], 0.0)
        self.assertAlmostEqual(w['equity'], 0.84)
        self.assertAlmostEqual(sum(w.values()), 1.0)

    def test_ablation_weights_renormalize(self):
        w = mr.normalized(mr.GOLD_WEIGHTS, 'real_yield')
        self.assertAlmostEqual(sum(w.values()), 1.0)
        self.assertNotIn('real_yield', w)

    def test_target_mapping_respects_declared_ranges(self):
        gold = {k: 1.0 for k in mr.GOLD_WEIGHTS}
        silver = {k: -1.0 for k in mr.SILVER_WEIGHTS}
        g, s, _, _ = mr.target_from_components(gold, silver)
        self.assertTrue(0.08 <= g <= 0.18)
        self.assertTrue(0.0 <= s <= 0.07)


if __name__ == '__main__':
    unittest.main()
