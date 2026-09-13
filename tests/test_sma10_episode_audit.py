import sys
import unittest
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import sma10_episode_audit as s  # noqa: E402


class SMA10EpisodeAuditTests(unittest.TestCase):
    def test_drawdown_episode_tracks_peak_trough_recovery(self):
        idx=pd.date_range('2020-01-01',periods=7,freq='D')
        df=pd.DataFrame({'value':[100,110,100,90,105,112,111]},index=idx)
        rows=s.drawdown_episodes(df)
        self.assertGreaterEqual(len(rows),1)
        first=rows[0]
        self.assertEqual(first['peak_date'],idx[1])
        self.assertEqual(first['trough_date'],idx[3])
        self.assertEqual(first['recovery_date'],idx[5])
        self.assertAlmostEqual(first['drawdown_pct'],100*(90/110-1),places=12)

    def test_transition_helpers_do_not_invent_state(self):
        idx=pd.to_datetime(['2020-01-02','2020-02-03','2020-03-02','2020-04-01'])
        execs=pd.DataFrame({'risk_off':[False,False,True,False]},index=idx)
        tr=s.state_transitions(execs)
        self.assertFalse(s.state_on(execs,pd.Timestamp('2020-02-15')))
        self.assertTrue(s.state_on(execs,pd.Timestamp('2020-03-15')))
        self.assertEqual(s.first_riskoff_between(tr,pd.Timestamp('2020-02-01'),pd.Timestamp('2020-03-31')),pd.Timestamp('2020-03-02'))
        self.assertEqual(s.transition_after(tr,pd.Timestamp('2020-03-02'),False),pd.Timestamp('2020-04-01'))


if __name__=='__main__':unittest.main()
