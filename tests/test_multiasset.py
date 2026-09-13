import sys,unittest,json
from pathlib import Path
from datetime import date
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import multiasset as ma

class MultiAssetTests(unittest.TestCase):
 def latest(self):
  today=str(date.today())
  d=json.loads((Path(__file__).resolve().parent/'fixtures/live_packet.json').read_text())
  d['model_version']='3.12-evidence-first-1';d['generated_at']=today+'T00:00:00+00:00';d['nifty']['date']=today;d['nifty']['gsec_meta']['asof']=today
  d['earnings']['asof']=today
  for f in d['macro']['factors'].values():f['asof']=today
  d['macro']['china_pmi']['asof']=today
  for f in d['macro']['domestic']['factors'].values():f['asof']=today
  d['trend']={'status':'live','policy_id':'trend-sma10-minus20-v1','asof':today,'completed_month':'fixture','completed_month_close':24000.0,'sma10':23500.0,'lookback_months':10,'risk_off':False,'risk_off_adjustment_pp':0}
  return d
 def market(self):
  dates=pd.date_range(end=pd.Timestamp(date.today()),periods=800,freq='D')
  def series(a,b,source):
   q=pd.DataFrame({'date':dates,'value':np.linspace(a,b,len(dates))});q.attrs={'asof':str(dates[-1].date()),'source':source};return q
  return {'gold':series(1800,2500,'gold'),'silver':series(22,31,'silver'),'btc':series(30000,65000,'btc')}
 def test_core_sums_to_100_and_btc_is_separate(self):
  d=self.latest();out=ma.build(d,self.market());self.assertEqual(out['status'],'live')
  self.assertEqual(out['source_latest_generated_at'],d['generated_at'])
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
 def test_missing_macro_factor_is_never_neutral_filled_in_metals_layer(self):
  d=self.latest();d['macro']['factors']['us_real_10y']['status']='unavailable'
  with self.assertRaises(RuntimeError):ma.build(d,self.market())
 def test_btc_drawdown_value_is_positive_when_far_below_high(self):
  d=self.latest();btc={'vs_ma200_pct':-5,'momentum_12m_pct':-10,'drawdown_from_3y_high_pct':-60,'asof':str(date.today())}
  out=ma.btc_model(d,btc)
  self.assertGreater(out['drivers']['drawdown_value']['score'],0)
 def test_core_signal_matches_existing_formula_shape(self):
  x=ma.latest_core_signal(self.latest())
  self.assertTrue(0<=x['equity_pct']<=100);self.assertAlmostEqual(x['equity_pct']+x['debt_pct'],100)
 def test_stale_macro_does_not_block_v312_core_but_still_blocks_macro_dependent_metals(self):
  d=self.latest();d['macro']['factors']['vix']['asof']='2000-01-01'
  x=ma.latest_core_signal(d)
  self.assertTrue(0<=x['equity_pct']<=100)
  with self.assertRaises(RuntimeError):ma.build(d,self.market())
 def test_missing_primary_snapshot_timestamp_is_rejected(self):
  d=self.latest();d.pop('generated_at')
  with self.assertRaises(RuntimeError):ma.build(d,self.market())
 def test_missing_trend_blocks_multiasset_core_too(self):
  d=self.latest();d.pop('trend')
  with self.assertRaises(RuntimeError):ma.latest_core_signal(d)

if __name__=='__main__':unittest.main()
