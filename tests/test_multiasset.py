import sys,unittest
from pathlib import Path
from datetime import date
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import multiasset as ma

class MultiAssetTests(unittest.TestCase):
 def latest(self):
  today=str(date.today())
  return {
   'generated_at':today+'T00:00:00+00:00',
   'nifty':{'pe':19.78,'pb':2.83,'div_yield':1.21,'gsec10':6.97},
   'earnings':{'score':-.29,'coverage':1},
   'macro':{
    'score':-.04,'active_block_weight':1,
    'blocks':{'global_liquidity':-.15},
    'factors':{
      'us_real_10y':{'status':'live','value':2.6,'asof':today},
      'usd_3m_pct':{'status':'live','value':.06,'asof':today},
      'vix':{'status':'live','value':16,'asof':today},
    },
    'china_pmi':{'status':'live','coverage':1,'score':.02,'pmi':50.2,'new_orders':50.4,'asof':today}
   }
  }
 def market(self):
  dates=pd.date_range(end=pd.Timestamp(date.today()),periods=800,freq='D')
  def series(a,b,source):
   q=pd.DataFrame({'date':dates,'value':np.linspace(a,b,len(dates))});q.attrs={'asof':str(dates[-1].date()),'source':source};return q
  return {'gold':series(1800,2500,'gold'),'silver':series(22,31,'silver'),'btc':series(30000,65000,'btc')}
 def test_core_sums_to_100_and_btc_is_separate(self):
  out=ma.build(self.latest(),self.market());self.assertEqual(out['status'],'live')
  self.assertAlmostEqual(sum(out['core_allocation'].values()),100)
  self.assertFalse(out['btc']['included_in_core_100pct'])
  self.assertIn(out['btc']['tactical_signal_pct'],[0,2.5,5,7.5,10])
 def test_metals_respect_declared_ranges(self):
  out=ma.build(self.latest(),self.market())
  self.assertTrue(8<=out['gold']['target_pct']<=18)
  self.assertTrue(0<=out['silver']['target_pct']<=7)
  self.assertLessEqual(out['gold']['target_pct']+out['silver']['target_pct'],25)
 def test_metals_preserve_original_equity_debt_ratio(self):
  out=ma.build(self.latest(),self.market());before=out['core_signal_before_metals'];after=out['core_allocation']
  self.assertAlmostEqual(after['equity_pct']/after['debt_pct'],before['equity_pct']/before['debt_pct'])
 def test_missing_macro_factor_is_never_neutral_filled(self):
  d=self.latest();d['macro']['factors']['us_real_10y']['status']='unavailable'
  with self.assertRaises(RuntimeError):ma.build(d,self.market())
 def test_btc_drawdown_value_is_positive_when_far_below_high(self):
  d=self.latest();btc={'vs_ma200_pct':-5,'momentum_12m_pct':-10,'drawdown_from_3y_high_pct':-60,'asof':str(date.today())}
  out=ma.btc_model(d,btc)
  self.assertGreater(out['drivers']['drawdown_value']['score'],0)
 def test_core_signal_matches_existing_formula_shape(self):
  x=ma.latest_core_signal(self.latest())
  self.assertTrue(0<=x['equity_pct']<=100);self.assertAlmostEqual(x['equity_pct']+x['debt_pct'],100)

if __name__=='__main__':unittest.main()
