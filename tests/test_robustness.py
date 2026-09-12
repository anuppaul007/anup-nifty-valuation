import json,sys,unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import robustness_audit as a

class RobustnessTests(unittest.TestCase):
 def panel(self):
  n=60;idx=pd.period_range('2021-04',periods=n,freq='M')
  return pd.DataFrame({'pe':[20+i*.03+(i%7)*.2 for i in range(n)],'pb':[3+i*.005+(i%5)*.03 for i in range(n)],'dy':[1.2+(i%9)*.02 for i in range(n)],'gsec10':[6+(i%11)*.04 for i in range(n)],'equity_tri':[100*1.005**i for i in range(n)],'debt_tri':[100*1.003**i for i in range(n)]},index=idx)
 def test_future_changes_do_not_rewrite_earlier_calibration(self):
  p=self.panel();original=a.calibrated_weights(p,36);p.iloc[50:,p.columns.get_loc('pe')]=100
  modified=a.calibrated_weights(p,36)
  pd.testing.assert_series_equal(original.iloc[:50],modified.iloc[:50])
 def test_fixed_balanced_portfolio_pays_drift_rebalancing_cost(self):
  p=self.panel();w=pd.Series(.6,index=p.index)
  self.assertLess(a.performance(p,w,.005)['cagr_pct'],a.performance(p,w,0)['cagr_pct'])

if __name__=='__main__':unittest.main()
