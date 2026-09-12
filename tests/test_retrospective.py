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
  for k in r.CURVES:
   self.assertAlmostEqual(r.curve(-r.C['zc'],k),100);self.assertAlmostEqual(r.curve(r.C['zc'],k),0)
   self.assertGreater(r.curve(-1,k),r.curve(0,k));self.assertGreater(r.curve(0,k),r.curve(1,k))
 def test_signal_is_applied_to_next_month_only(self):
  p=self.panel();frame,gross,net,z=r.strategy_returns(p,1.0)
  self.assertEqual(len(frame),3)
  first_w=float(frame.w.iloc[0]);expected=first_w*.10+(1-first_w)*.01
  self.assertAlmostEqual(float(gross.iloc[0]),expected)
  self.assertEqual(str(frame.index[0]),'2024-01');self.assertEqual(str(frame.index[-1]),'2024-03')
 def test_turnover_cost_never_improves_return(self):
  p=self.panel();frame,gross,net,z=r.strategy_returns(p,1.35)
  self.assertTrue((net<=gross+1e-15).all())
 def test_fixed_100_equity_matches_equity_tri_returns(self):
  p=self.panel();x=r.fixed_returns(p,1.0)
  expected=p.equity_tri.pct_change().shift(-1).dropna()
  self.assertEqual(len(x),len(expected));self.assertAlmostEqual(float((x-expected).abs().max()),0)

if __name__=='__main__':unittest.main()
