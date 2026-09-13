import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import benchmark_audit as ba  # noqa: E402


class BenchmarkAuditTests(unittest.TestCase):
    def test_max_drawdown_uses_initial_wealth(self):
        self.assertAlmostEqual(ba.max_drawdown_pct(np.array([-0.10,0.20])), -10.0, places=12)

    def test_observed_effect_horizon_is_longer_after_efficiency_penalty(self):
        rng=np.random.default_rng(7)
        x=pd.Series(0.0001+rng.normal(0,0.01,72))
        q=ba.observed_effect_horizon(x)
        if q['status']=='heuristic_only':
            self.assertGreaterEqual(q['serial_dependence_adjusted_years_if_same_efficiency_persisted'],q['raw_years_if_iid_effect_persisted'])

    def test_comparator_marks_ex_ante_status(self):
        idx=pd.period_range('2020-01',periods=24,freq='M')
        eq=pd.Series(np.full(24,0.01),index=idx);db=pd.Series(np.full(24,0.002),index=idx)
        dyn=pd.Series(np.full(24,0.006),index=idx)
        q=ba.describe_comparator('x',np.full(24,.5),dyn,eq,db,True,'fixture')
        self.assertTrue(q['available_ex_ante'])
        self.assertIn('dynamic_minus_comparator_cagr_pp',q)
        self.assertIn('dynamic_additional_drawdown_pp',q)

    def test_beta_signature_centers_on_dynamic_mean(self):
        comps={
          'expanding_mean_investable':{'comparator_mean_equity_pct':40,'dynamic_minus_comparator_cagr_pp':2.0},
          'ex_post_realised_mean_static':{'comparator_mean_equity_pct':50,'dynamic_minus_comparator_cagr_pp':1.0},
          'fixed_60_40_policy':{'comparator_mean_equity_pct':60,'dynamic_minus_comparator_cagr_pp':0.0},
        }
        q=ba.comparator_beta_signature(comps,50)
        self.assertTrue(q['monotone_decreasing_excess_cagr_with_comparator_equity'])
        self.assertAlmostEqual(q['slope_pp_excess_cagr_per_1pp_comparator_equity'],-0.1,places=12)
        self.assertAlmostEqual(q['fitted_excess_cagr_at_dynamic_mean_equity_pp'],1.0,places=12)
        self.assertAlmostEqual(q['fitted_zero_cross_equity_pct'],60.0,places=12)


if __name__=='__main__':unittest.main()
