import sys,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import walkforward as w

class WalkForwardTests(unittest.TestCase):
 def fixture(self):
  d=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/live_packet.json').read_text())
  d['generated_at']='2026-09-12T03:05:49Z'
  d['model_version']='3.10-pb-regime-1'
  return d
 def test_incomplete_macro_never_enters_prospective_ledger(self):
  d=self.fixture();d['macro']['active_block_weight']=.99;self.assertIsNone(w.model_snapshot(d,now="2026-09-12T12:00:00Z"))
  d=self.fixture();d['macro']['domestic']['status']='unavailable';self.assertIsNone(w.model_snapshot(d,now="2026-09-12T12:00:00Z"))
 def test_candidate_caps_do_not_change_live_parameters(self):
  s=w.model_snapshot(self.fixture(),now="2026-09-12T12:00:00Z");self.assertIsNotNone(s);self.assertEqual(set(s['candidate_equity_targets']),{'0','3','6','9','12','15'})
  self.assertLess(s['candidate_equity_targets']['15'],s['candidate_equity_targets']['0'])
 def test_curve_candidates_are_recorded_but_live_slope_stays_135(self):
  s=w.model_snapshot(self.fixture(),now="2026-09-12T12:00:00Z");self.assertEqual(set(s['candidate_curve_targets']),{'0.6','0.8','1.0','1.15','1.35','1.5'})
  self.assertAlmostEqual(s['candidate_curve_targets']['1.35'],s['candidate_equity_targets']['6'])
  self.assertLess(s['candidate_curve_targets']['0.6'],s['candidate_curve_targets']['1.35']);self.assertGreater(s['empirical_valuation_cheapness'],70)
 def test_extreme_candidates_are_recorded_but_live_zc_stays_25(self):
  s=w.model_snapshot(self.fixture(),now="2026-09-12T12:00:00Z");self.assertEqual(set(s['candidate_extreme_targets']),{'2.5','3.0','3.5','4.0'})
  self.assertAlmostEqual(s['candidate_extreme_targets']['2.5'],s['candidate_equity_targets']['6'])
  self.assertLess(s['candidate_extreme_targets']['4.0'],s['candidate_extreme_targets']['2.5'])
  self.assertEqual(len(s['candidate_grid_targets']),len(w.CANDIDATE_CURVE_SLOPES)*len(w.CANDIDATE_EXTREMES))
 def test_outcomes_never_use_partial_current_month(self):
  records=[{'month':'2026-03','nifty_level':20000,'forward_nifty_price_return_6m':None,'forward_nifty_price_return_12m':None},{'month':'2026-09','nifty_level':22000,'forward_nifty_price_return_6m':None,'forward_nifty_price_return_12m':None}]
  out=w.update_outcomes(records,'2026-09');self.assertIsNone(out[0]['forward_nifty_price_return_6m'])
  out=w.update_outcomes(records,'2026-10');self.assertAlmostEqual(out[0]['forward_nifty_price_return_6m'],10)
 def test_parameter_change_gate_is_deliberately_slow(self):
  short=[{'month':f'2020-{i:02d}','forward_nifty_price_return_6m':1,'forward_nifty_price_return_12m':1} for i in range(1,13)]
  s=w.summary(short);self.assertFalse(s['eligible_for_parameter_change']);self.assertIn('zc=2.5',s['parameter_lock'])

 def test_stale_packet_cannot_enter_ledger(self):
  d=self.fixture();d['generated_at']='2026-01-01';self.assertIsNone(w.model_snapshot(d,now='2026-09-12T12:00:00Z'))
 def test_candidate_extreme_uses_its_own_damping(self):
  d=self.fixture();s=w.model_snapshot(d,now='2026-09-12T12:00:00Z');z=s['valuation_z'];zc=4.0
  expected=w.curve(z,1.35,zc)+(d['earnings']['score']*6+d['macro']['score']*6)*max(0,1-abs(z)/zc)
  self.assertAlmostEqual(s['candidate_extreme_targets']['4.0'],expected)

if __name__=='__main__':unittest.main()
