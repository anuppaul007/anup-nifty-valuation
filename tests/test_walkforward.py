import sys,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import walkforward as w

class WalkForwardTests(unittest.TestCase):
 def fixture(self):
  d=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/live_packet.json').read_text())
  d['generated_at']='2026-09-12T03:05:49Z'
  d['model_version']='3.13-reliability-1'
  return d
 def test_incomplete_macro_still_records_live_decision_but_not_shadow_candidates(self):
  d=self.fixture();d['macro']['active_block_weight']=.99;s=w.model_snapshot(d,now="2026-09-12T12:00:00Z");self.assertIsNotNone(s);self.assertFalse(s['macro_context_eligible']);self.assertTrue(all(v is None for v in s['candidate_equity_targets'].values()))
  d=self.fixture();d['macro']['domestic']['status']='unavailable';s=w.model_snapshot(d,now="2026-09-12T12:00:00Z");self.assertIsNotNone(s);self.assertFalse(s['macro_context_eligible'])
 def test_macro_shadow_candidates_do_not_change_live_parameters(self):
  s=w.model_snapshot(self.fixture(),now="2026-09-12T12:00:00Z");self.assertIsNotNone(s);self.assertEqual(set(s['candidate_equity_targets']),{'0','3','6','9','12','15'})
  self.assertAlmostEqual(s['candidate_equity_targets']['0'],s['live_equity_target']);self.assertNotEqual(s['candidate_equity_targets']['15'],s['candidate_equity_targets']['0']);self.assertEqual(s['macro_adjustment_pp'],0.0)
 def test_curve_candidates_are_recorded_with_zero_live_macro_authority(self):
  s=w.model_snapshot(self.fixture(),now="2026-09-12T12:00:00Z");self.assertEqual(set(s['candidate_curve_targets']),{'0.6','0.8','1.0','1.15','1.35','1.5'})
  self.assertAlmostEqual(s['candidate_curve_targets']['1.35'],s['live_equity_target']);self.assertGreater(s['empirical_valuation_cheapness'],70)
 def test_extreme_candidates_use_live_zero_macro_authority(self):
  s=w.model_snapshot(self.fixture(),now="2026-09-12T12:00:00Z");self.assertEqual(set(s['candidate_extreme_targets']),{'2.5','3.0','3.5','4.0'})
  self.assertAlmostEqual(s['candidate_extreme_targets']['2.5'],s['live_equity_target'])
  self.assertEqual(len(s['candidate_grid_targets']),len(w.CANDIDATE_CURVE_SLOPES)*len(w.CANDIDATE_EXTREMES))
 def test_outcomes_never_use_partial_current_month(self):
  records=[{'month':'2026-03','nifty_level':20000,'forward_nifty_price_return_6m':None,'forward_nifty_price_return_12m':None},{'month':'2026-09','nifty_level':22000,'forward_nifty_price_return_6m':None,'forward_nifty_price_return_12m':None}]
  out=w.update_outcomes(records,'2026-09');self.assertIsNone(out[0]['forward_nifty_price_return_6m'])
  out=w.update_outcomes(records,'2026-10');self.assertAlmostEqual(out[0]['forward_nifty_price_return_6m'],10)
 def test_parameter_change_gate_is_deliberately_slow(self):
  short=[{'month':f'2020-{i:02d}','forward_nifty_price_return_6m':1,'forward_nifty_price_return_12m':1} for i in range(1,13)]
  s=w.summary(short);self.assertFalse(s['eligible_for_parameter_change']);self.assertIn('live macro 0 pp',s['parameter_lock'])
 def test_stale_packet_cannot_enter_ledger(self):
  d=self.fixture();d['generated_at']='2026-01-01';self.assertIsNone(w.model_snapshot(d,now='2026-09-12T12:00:00Z'))
 def test_candidate_extreme_uses_only_live_earnings_authority(self):
  d=self.fixture();s=w.model_snapshot(d,now='2026-09-12T12:00:00Z');z=s['valuation_z'];zc=4.0
  expected=w.curve(z,1.35,zc)+d['earnings']['score']*6*w.overlay_damp(z,zc)
  self.assertAlmostEqual(s['candidate_extreme_targets']['4.0'],expected)
 def test_risk_off_trend_is_recorded_without_rewriting_candidate_family(self):
  d=self.fixture();d['trend']['completed_month_close']=22000;d['trend']['sma10']=23500;d['trend']['risk_off']=True;d['trend']['risk_off_adjustment_pp']=-20
  for i,r in enumerate(d['trend']['monthly_closes']):r['close']=22000 if i==9 else (235000-22000)/9
  s=w.model_snapshot(d,now='2026-09-12T12:00:00Z');self.assertTrue(s['trend_risk_off']);self.assertEqual(s['trend_adjustment_pp'],-20);self.assertLess(s['live_equity_target'],100)

if __name__=='__main__':unittest.main()
