import sys,unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import retrospective_core as r

class RetrospectiveTests(unittest.TestCase):
 def panel(self):
  idx=pd.period_range('2024-01','2024-04',freq='M')
  return pd.DataFrame({'pe':[22,21,20,19],'pb':[3.9,3.7,3.5,3.3],'dy':[1.2,1.25,1.3,1.35],'gsec10':[7,7,7,7],
                       'equity_tri':[100,110,99,108.9],'debt_tri':[100,101,102.01,103.0301]},index=idx)
 def test_curve_endpoints_and_cheapness_monotonicity(self):
  for zc in r.EXTREMES:
   for k in r.CURVES:
    self.assertAlmostEqual(r.curve(-zc,k,zc),100);self.assertAlmostEqual(r.curve(zc,k,zc),0)
    self.assertGreater(r.curve(-1,k,zc),r.curve(0,k,zc));self.assertGreater(r.curve(0,k,zc),r.curve(1,k,zc))
 def test_wider_extreme_threshold_is_less_aggressive_inside_range(self):
  self.assertLess(r.curve(-1,r.LIVE_K,4.0),r.curve(-1,r.LIVE_K,2.5))
  self.assertGreater(r.curve(1,r.LIVE_K,4.0),r.curve(1,r.LIVE_K,2.5))
 def test_signal_is_applied_to_next_month_only(self):
  p=self.panel();frame,gross,net,z=r.strategy_returns(p,1.0,3.0)
  self.assertEqual(len(frame),3)
  first_w=float(frame.w.iloc[0]);expected=first_w*.10+(1-first_w)*.01
  self.assertAlmostEqual(float(gross.iloc[0]),expected)
  self.assertEqual(str(frame.index[0]),'2024-01');self.assertEqual(str(frame.index[-1]),'2024-03')
 def test_turnover_cost_never_improves_return(self):
  p=self.panel();frame,gross,net,z=r.strategy_returns(p,1.35,2.5)
  self.assertTrue((net<=gross+1e-15).all())
 def test_fixed_100_equity_matches_equity_tri_returns(self):
  p=self.panel();x=r.fixed_returns(p,1.0)
  expected=p.equity_tri.pct_change().shift(-1).dropna()
  self.assertEqual(len(x),len(expected));self.assertAlmostEqual(float((x-expected).abs().max()),0)
 def test_sortino_is_dimensionless_not_percent_scaled(self):
  s=r.stats([.01,-.01,.02,-.005,.015,.003])
  self.assertIn('sortino_0',s);self.assertNotIn('sortino_0_pct',s);self.assertLess(abs(s['sortino_0']),20)
 def test_grid_keys_are_unique(self):
  keys={r.grid_key(k,zc) for zc in r.EXTREMES for k in r.CURVES}
  self.assertEqual(len(keys),len(r.EXTREMES)*len(r.CURVES))

 def test_first_month_loss_is_a_drawdown(self):
  self.assertAlmostEqual(r.max_drawdown([-.2,.1]),-.2)
 def test_flat_target_still_requires_rebalancing_after_different_returns(self):
  self.assertAlmostEqual(r.rebalance_turnover([.5,.5],[.2,0],[0,0])[1],.5*1.2/1.1-.5)
 def test_missing_calendar_month_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'Missing calendar month'):r.strategy_returns(self.panel().drop(pd.Period('2024-02','M')))

if __name__=='__main__':unittest.main()
