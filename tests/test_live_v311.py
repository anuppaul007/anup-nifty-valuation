import sys, unittest
from pathlib import Path
from unittest.mock import patch
from datetime import date, timedelta

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import update_data_v3 as u


class LiveV311Tests(unittest.TestCase):
    def test_trend_uses_only_completed_months(self):
        today=date.today()
        rows=[]
        # Build 12 completed months plus a deliberately extreme current-month value.
        start=(today.replace(day=1)-timedelta(days=380))
        d=start
        level=100.0
        while d<=today:
            if d.weekday()<5:
                level+=0.1
                rows.append({'Date':d.isoformat(),'Close':level})
            d+=timedelta(days=1)
        rows.append({'Date':today.isoformat(),'Close':99999.0})
        with patch('jugaad_data.nse.index_raw',return_value=rows):
            x=u.nifty_trend()
        self.assertEqual(x['status'],'live')
        self.assertEqual(x['policy_id'],'trend-sma10-minus20-v1')
        self.assertEqual(x['lookback_months'],10)
        self.assertNotEqual(x['completed_month_close'],99999.0)
        self.assertEqual(x['risk_off'],x['completed_month_close']<x['sma10'])
        self.assertEqual(x['risk_off_adjustment_pp'],-20 if x['risk_off'] else 0)

    def test_trend_rejects_missing_month_even_with_enough_daily_rows(self):
        import pandas as pd
        today=date.today();missing=str(pd.Period(today,freq='M')-4)
        rows=[{'Date':str(d.date()),'Close':100.0} for d in pd.date_range(today-timedelta(days=580),today,freq='B') if str(d.to_period('M'))!=missing]
        with patch('jugaad_data.nse.index_raw',return_value=rows):x=u.nifty_trend()
        self.assertEqual(x['status'],'unavailable')
        self.assertIn('consecutive',x['error'])

    def test_trend_fails_closed_when_history_is_insufficient(self):
        with patch('jugaad_data.nse.index_raw',return_value=[]):
            x=u.nifty_trend()
        self.assertEqual(x['status'],'unavailable')
        self.assertIsNone(x['risk_off'])
        self.assertIsNone(x['risk_off_adjustment_pp'])


if __name__=='__main__':unittest.main()
