from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import current_definition_anchor_validation as a


def test_dividend_rupees_per_share():
    assert a.parse_dividend('Final Dividend - Rs 9 Per Share',10)==9.0
    assert a.parse_dividend('Interim Dividend - Rs. 18.50 Per Share',5)==18.5


def test_dividend_percent_fallback_uses_face_value():
    assert a.parse_dividend('Dividend - 200%',5)==10.0


def test_non_dividend_ignored():
    assert a.parse_dividend('Demerger',10) is None


def test_period_fact_selection_exact():
    xml='''<xbrl xmlns:x="urn:x"><context id="Q"><period><startDate>2023-04-01</startDate><endDate>2023-06-30</endDate></period></context><x:ProfitLossForPeriod contextRef="Q">123</x:ProfitLossForPeriod></xbrl>'''
    fs=a.facts(ET.fromstring(xml));f=a.pick_fact(fs,['ProfitLossForPeriod'],'2023-04-01','2023-06-30')
    assert f and f['value']==123


def test_yield_aggregation_identity():
    rows=[{'weight':0.6,'earnings_yield':0.05,'book_yield':0.25,'dividend_yield_pct':1.0},
          {'weight':0.4,'earnings_yield':0.10,'book_yield':0.50,'dividend_yield_pct':2.0}]
    pe=1/sum(r['weight']*r['earnings_yield'] for r in rows)
    pb=1/sum(r['weight']*r['book_yield'] for r in rows)
    dy=sum(r['weight']*r['dividend_yield_pct'] for r in rows)
    assert round(pe,8)==round(1/0.07,8)
    assert round(pb,8)==round(1/0.35,8)
    assert dy==1.4


def test_tolerances_are_predeclared_and_tight():
    assert a.TOL=={'pe_relative_pct':1.5,'pb_relative_pct':1.5,'dy_absolute_pp':0.05}
