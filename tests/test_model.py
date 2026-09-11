import sys, unittest, math
from pathlib import Path
from unittest.mock import patch
from datetime import date,timedelta
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import macro_v3 as m
import update_data_v3 as updater

STOXX='''<html><p>all data as of July 31, 2026</p>
<table><tr><th>Index volatility and risk</th><th>1Y volatility</th><th>3Y</th><th>5Y</th><th>Sharpe 1Y</th><th>Sharpe 3Y</th><th>Sharpe 5Y</th></tr>
<tr><td>STOXX Emerging Markets ex India Universal All Cap</td><td>23.9</td><td>18.9</td><td>18.7</td><td>1.3</td><td>0.8</td><td>0.3</td></tr></table>
<table><thead><tr><th rowspan="2">Index</th><th colspan="2">Price/earnings incl. negative</th><th colspan="2">Price/earnings excl. negative</th><th>Price/book</th><th>Dividend yield (%)</th></tr>
<tr><th>Trailing</th><th>Projected</th><th>Trailing</th><th>Projected</th><th>Trailing</th><th>Trailing</th></tr></thead><tbody>
<tr><td>STOXX Emerging Markets ex India Universal All Cap</td><td>17.2</td><td>10.9</td><td>15.3</td><td>10.6</td><td>2.1</td><td>3.1</td></tr></tbody></table></html>'''

class ModelTests(unittest.TestCase):
 def test_rbi_binds_bond_yield_to_its_own_date_not_coupon_or_fx_date(self):
  text='<p>Exchange Rates As at September 11, 2026</p><h3>Government Securities Market</h3><p>6.36% GS 2031 : 6.5231% #</p><p>6.94% GS 2036 : 6.9711% #</p><p>7.06% GS 2041 : 7.1121% #</p><p># as on September 10, 2026</p><h3>Capital Market</h3>'
  value,meta=updater.parse_rbi_yield(text)
  self.assertEqual(value,6.9711);self.assertEqual(meta['asof'],'2026-09-10')
  self.assertEqual(meta['security'],'6.94% GS 2036')
  with self.assertRaises(RuntimeError):updater.parse_rbi_yield(text.replace('# as on September 10, 2026',''))
 def test_stoxx_binds_fundamentals_not_risk_table(self):
  x=m.parse_stoxx(STOXX)
  self.assertEqual((x['pe'],x['pb'],x['div_yield']),(17.2,2.1,3.1))
  self.assertEqual(x['asof'],'2026-07-31')
 def test_missing_history_is_not_neutral(self):
  self.assertIsNone(m.rz([1,2,3],24))
  self.assertIsNone(m.rz([1]*100,24))
  self.assertEqual(m.weighted([(None,.5),(None,.5)]),(None,0))
 def test_china_missing_orders_reduces_coverage(self):
  period=str(pd.Period(date.today(),freq='M')-1)
  x=m.parse_china('<p>manufacturing industry was 49.8%</p>',period)
  self.assertEqual(x['coverage'],.7)
  self.assertAlmostEqual(x['score'],m.squash((49.8-50)/1.75))
 def test_coverage_arithmetic_matches_quote(self):
  mac={'blocks':{'global_liquidity':-.5910131508030626,'india_external_carry':-.291777058540953,'china_industrial':.006666567902989752,'relative_em_valuation':None},'factor_coverage':{'global_liquidity':.75,'india_external_carry':.35,'china_industrial':1,'relative_em_valuation':0}}
  m.coverage_adjust_macro(mac)
  self.assertAlmostEqual(mac['active_block_weight'],.53)
  self.assertAlmostEqual(mac['score'],-.3061910122582852)
 def test_build_failure_invalidates_old_active_scores(self):
  x=updater.unavailable_macro({'macro':{'score':1,'active_block_weight':1,'blocks':{'global_liquidity':1}}},'timeout')
  self.assertIsNone(x['score']);self.assertEqual(x['active_block_weight'],0)
 def test_stale_future_and_undated_data_are_excluded(self):
  for dt in [None,str(date.today()+timedelta(days=1)),str(date.today()-timedelta(days=15))]:
   self.assertFalse(m.fresh(dt,7))
 def test_corrected_em_history_aligns_month_and_deduplicates(self):
  cur=m.parse_stoxx(STOXX)
  old={'calibration':{'em_ex_india_history':[{'month':'2026-09','em_pe':23.9,'em_pb':.8,'relative_log_premium':.4}]}}
  with patch.object(m,'stoxx',return_value=cur):
   for _ in range(25):
    out,h=m.relative_em({'pe':19.85,'pb':2.84},[['2026-07',20.78,2.99,1.22],['2026-09',19.85,2.84,1.21]],old)
    old={'calibration':{'em_ex_india_history':h}}
  self.assertEqual(len(h),1);self.assertEqual(h[0]['month'],'2026-07')
  self.assertEqual(h[0]['nifty_pe'],20.78);self.assertIsNone(out['score'])
 def test_fed_real_csv_is_parsed_as_csv(self):
  class Response:
   text='Metadata,ignored\nTime Period,Series value\n2026-08-01,100\n2026-09-01,101\n'
   def raise_for_status(self):pass
  with patch.object(m.requests,'get',return_value=Response()):
   x=m._fed_table('https://example.org','series')
  self.assertEqual(x.value.tolist(),[100,101])
 def test_fed_csv_quoted_header_selects_named_series(self):
  text='"Series Description","Nominal Advanced Foreign Economies Dollar Index","Nominal Broad Dollar Index"\n"Time Period","ADV","BROAD"\n2026-07,900,120\n2026-08,901,118\n'
  x=m._fed_csv(text,'Nominal Broad Dollar Index','fixture')
  self.assertEqual(x.value.tolist(),[120,118])
 def test_dollar_momentum_uses_completed_months(self):
  month=pd.Timestamp(date.today().replace(day=1))
  df=pd.DataFrame({'date':[month-pd.DateOffset(months=2),month-pd.DateOffset(months=1),month],'value':[99,100,1000]})
  with patch.object(m,'fred_optional',return_value=df):x=m.fed_broad_usd()
  self.assertEqual(x.value.iloc[-1],100)
  self.assertEqual(x.attrs['asof'],str((month-pd.Timedelta(days=1)).date()))
 def test_optional_source_failure_keeps_other_scores(self):
  df=pd.DataFrame({'date':pd.date_range(end=pd.Timestamp(date.today()),periods=130),'value':[2+i*.01+math.sin(i)*.05 for i in range(130)]})
  df.attrs={'asof':str(date.today()),'source':'test fixture'}
  with patch.object(m,'treasury_curve',return_value=df),patch.object(m,'fed_broad_usd',return_value=None),patch.object(m,'fed_assets',side_effect=TimeoutError('fixture')),patch.object(m,'cboe_vix',return_value=df),patch.object(m,'yahoo_series',return_value=df),patch.object(m,'fred_optional',return_value=None),patch.object(m,'china_pmi',return_value=None),patch.object(m,'relative_em',return_value=({'score':None},[])):
   mac,_=m.build(None,{},[],{})
  self.assertIsNotNone(mac['blocks']['global_liquidity'])
  self.assertGreater(mac['active_block_weight'],0)
  self.assertIsNone(mac['factors']['fed_assets_6m_pct']['score'])

if __name__=='__main__':unittest.main()
