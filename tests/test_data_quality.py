import unittest,sys,json,subprocess
from pathlib import Path
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import data_quality as q
import macro_v3 as m
import valuation_diagnostics as vd

class QualityTests(unittest.TestCase):
 def test_em_anomaly_quarantined_even_if_current_fetch_fails(self):
  bad={'month':'2026-02','method':'largecap-fundamentals-v1','em_pe':17.3,'em_pb':.5,'nifty_pe':22.03,'nifty_pb':3.42,'relative_log_premium':.914}
  with patch.object(m,'stoxx',return_value=None):
   out,history=m.relative_em({},[],{'calibration':{'em_ex_india_history':[bad]}})
  self.assertEqual(history,[]);self.assertEqual(out['quarantine'][0]['record'],bad);self.assertIsNone(out['score'])
 def test_new_bad_em_archive_cannot_reenter_calibration(self):
  cur={'pe':16.,'pb':2.,'div_yield':2.,'asof':'2026-08-31','source_url':'source','method':'largecap-fundamentals-v1','pe_basis':'trailing'}
  bad=dict(cur,pe=17.3,pb=.5,asof='2026-02-27')
  with patch.object(m,'stoxx',side_effect=lambda month=None:bad if month else cur):
   out,hist=m.relative_em({},[['2026-02',22.03,3.42,1.2],['2026-08',20,3,1.2]],{})
  self.assertNotIn('2026-02',[r['month'] for r in hist]);self.assertTrue(out['quarantine'])
 def test_em_bounds_are_finite_and_consistent(self):
  for pe,pb in [(17.3,.5),(20,float('nan')),(20,8),(200,1)]:self.assertIsNotNone(q.em_issue({'pe':pe,'pb':pb}))
  self.assertIsNone(q.em_issue({'pe':16.3,'pb':2.4}))
 def test_documented_break_is_flagged_not_erased(self):
  e=q.ratio_breaks([['2023-08',22,4.4],['2023-09',22.24,3.46]])
  self.assertEqual(e[0]['status'],'documented_methodology_break')
  e=q.ratio_breaks([['2026-08',22,4.4],['2026-09',22.24,3.46]])
  self.assertEqual(e[0]['status'],'unresolved_ratio_break')
 def test_missing_months_not_mislabelled_as_monthly_jump(self):
  self.assertEqual(q.ratio_breaks([['2026-01',22,4.4],['2026-03',22.24,3.46]]),[])
 def test_bond_switch_is_preserved(self):
  old={'nifty':{'gsec_meta':{'security':'old bond','source':'RBI'}}}
  events,changed=q.security_transition(old,{'security':'new bond','source':'RBI','asof':'2026-09-11'})
  self.assertTrue(changed);self.assertEqual(events[0]['from_security'],'old bond')
  old['nifty']['gsec_meta']['security']='new bond';old['calibration']={'india_yield_transitions':events}
  more,changed=q.security_transition(old,{'security':'new bond','source':'RBI'})
  self.assertFalse(changed);self.assertEqual(more,events)
 def test_live_constants_reproduce_frozen_clean_sample(self):
  a=json.loads((ROOT/'data/pb_calibration_v3_10.json').read_text());rows=a['history']
  self.assertEqual(len(rows),36);self.assertEqual(rows[0][0],'2023-09');self.assertEqual(rows[-1][0],'2026-08')
  pb=np.array([r[2] for r in rows]);roe=np.array([100*r[2]/r[1] for r in rows])
  expected=dict(pbM=np.median(pb),pbS=np.std(pb),roeM=np.median(roe),roeS=np.std(roe))
  constants=json.loads(subprocess.check_output(['node','-e',"console.log(JSON.stringify(require('./model.js').C))"],cwd=ROOT,text=True))
  for k,v in expected.items():self.assertAlmostEqual(v,a['parameters'][k],12);self.assertAlmostEqual(v,constants[k],12)
 def test_diagnostic_excludes_old_pb_and_flags_divergence(self):
  h=[['2023-08',20,50,1]]+[[f'2024-{i:02}',20+i/10,3+i/10,1] for i in range(1,13)]
  d=vd.build(h,{'date':'2025-01-03','pe':10,'pb':2,'div_yield':.5})
  self.assertEqual(d['months'],12);self.assertLess(d['pb_stats']['max'],5);self.assertTrue(d['lens_disagreement']['flagged'])
if __name__=='__main__':unittest.main()
