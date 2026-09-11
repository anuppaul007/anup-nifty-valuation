import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import walkforward as w

class WalkForwardTests(unittest.TestCase):
 def fixture(self):
  return {'model_version':'3.6','generated_at':'2026-09-11T12:00:00Z','nifty':{'date':'2026-09-11','level':23398.1,'pe':19.78,'pb':2.83,'div_yield':1.21,'gsec10':6.97},'earnings':{'score':-.29,'coverage':1},'macro':{'score':-.05,'active_block_weight':1,'domestic':{'status':'live','score':.06},'blocks':{'global_liquidity':-.19,'india_external_carry':-.04,'india_domestic':.06,'china_industrial':.01}}}
 def test_incomplete_macro_never_enters_prospective_ledger(self):
  d=self.fixture();d['macro']['active_block_weight']=.99;self.assertIsNone(w.model_snapshot(d))
  d=self.fixture();d['macro']['domestic']['status']='unavailable';self.assertIsNone(w.model_snapshot(d))
 def test_candidate_caps_do_not_change_live_parameters(self):
  s=w.model_snapshot(self.fixture());self.assertIsNotNone(s);self.assertEqual(set(s['candidate_equity_targets']),{'0','3','6','9','12','15'})
  self.assertLess(s['candidate_equity_targets']['15'],s['candidate_equity_targets']['0'])
 def test_outcomes_never_use_partial_current_month(self):
  records=[{'month':'2026-03','nifty_level':20000,'forward_nifty_price_return_6m':None,'forward_nifty_price_return_12m':None},{'month':'2026-09','nifty_level':22000,'forward_nifty_price_return_6m':None,'forward_nifty_price_return_12m':None}]
  out=w.update_outcomes(records,'2026-09');self.assertIsNone(out[0]['forward_nifty_price_return_6m'])
  out=w.update_outcomes(records,'2026-10');self.assertAlmostEqual(out[0]['forward_nifty_price_return_6m'],10)
 def test_parameter_change_gate_is_deliberately_slow(self):
  short=[{'month':f'2020-{i:02d}','forward_nifty_price_return_6m':1,'forward_nifty_price_return_12m':1} for i in range(1,13)]
  self.assertFalse(w.summary(short)['eligible_for_parameter_change'])

if __name__=='__main__':unittest.main()
