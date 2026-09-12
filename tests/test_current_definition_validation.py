from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import current_definition_anchor_validation as legacy
import current_definition_integrated_anchor_v3 as hardened
ia=hardened.a


def test_dividend_rupees_per_share():
    assert legacy.parse_dividend('Final Dividend - Rs 9 Per Share',10)==9.0
    assert legacy.parse_dividend('Interim Dividend - Rs. 18.50 Per Share',5)==18.5


def test_dividend_percent_fallback_uses_face_value():
    assert legacy.parse_dividend('Dividend - 200%',5)==10.0


def test_non_dividend_ignored():
    assert legacy.parse_dividend('Demerger',10) is None


def test_period_fact_selection_exact():
    xml='''<xbrl xmlns:x="urn:x"><context id="Q"><period><startDate>2023-04-01</startDate><endDate>2023-06-30</endDate></period></context><x:ProfitLossForPeriod contextRef="Q">123</x:ProfitLossForPeriod></xbrl>'''
    fs=legacy.facts(ET.fromstring(xml));f=legacy.pick_fact(fs,['ProfitLossForPeriod'],'2023-04-01','2023-06-30')
    assert f and f['value']==123


def test_yield_aggregation_identity_and_signed_earnings():
    rows=[{'weight':0.6,'earnings_yield':0.05,'book_yield':0.25,'dividend_yield_pct':1.0},
          {'weight':0.4,'earnings_yield':-0.01,'book_yield':0.50,'dividend_yield_pct':2.0}]
    pe=1/sum(r['weight']*r['earnings_yield'] for r in rows)
    pb=1/sum(r['weight']*r['book_yield'] for r in rows)
    dy=sum(r['weight']*r['dividend_yield_pct'] for r in rows)
    assert round(pe,8)==round(1/0.026,8)
    assert round(pb,8)==round(1/0.35,8)
    assert dy==1.4


def test_tolerances_are_predeclared_and_unchanged():
    expected={'pe_relative_pct':1.5,'pb_relative_pct':1.5,'dy_absolute_pp':0.05}
    assert legacy.TOL==expected
    assert ia.TOL==expected


def _row(q,basis,when='2026-07-20'):
    return {'qe_Date':q,'consolidated':basis,'creation_Date':when,'xbrl':'x'}


def test_integrated_basis_prefers_consolidated():
    rows=[_row('30-JUN-2026','Standalone'),_row('30-JUN-2026','Consolidated')]
    chosen,basis=ia.choose_quarter(rows,'30-JUN-2026')
    assert basis=='consolidated'
    assert chosen['consolidated']=='Consolidated'


def test_integrated_basis_allows_standalone_only_when_consolidated_absent():
    rows=[_row('30-JUN-2026','Standalone')]
    chosen,basis=ia.choose_quarter(rows,'30-JUN-2026')
    assert chosen is not None and basis=='standalone_fallback'


def test_future_iso_filing_is_rejected_point_in_time():
    rows=[_row('30-JUN-2026','Consolidated','2026-09-01')]
    chosen,basis=ia.choose_quarter(rows,'30-JUN-2026')
    assert chosen is None and basis is None


def test_iso_date_is_not_day_month_inverted():
    assert str(ia.parse_dt('2026-09-01').date())=='2026-09-01'
    assert str(ia.parse_dt('20-Jul-2026').date())=='2026-07-20'


def test_zero_owner_placeholder_does_not_override_real_pat():
    fs=[
        {'name':'ProfitOrLossAttributableToOwnersOfParent','context':'OneD','value':0.0},
        {'name':'ProfitLossForPeriod','context':'OneD','value':958.68},
    ]
    f=ia.profit_from(fs)
    assert f['name']=='ProfitLossForPeriod' and f['value']==958.68


def test_negative_profit_is_valid_not_missing():
    fs=[{'name':'ProfitOrLossAttributableToOwnersOfParent','context':'OneD','value':-253.63}]
    assert ia.profit_from(fs)['value']==-253.63


def test_life_insurance_pat_tag_is_explicitly_supported():
    fs=[{'name':'ProfitLossAfterTaxAndExtraordinaryItems','context':'OneD','value':611.19}]
    assert ia.profit_from(fs)['value']==611.19


def test_direct_life_shareholders_funds_is_preferred():
    fs=[
        {'name':'ShareholdersFunds','context':'OneI','value':177.4954},
        {'name':'PaidUpEquityShareCapital','context':'OneI','value':21.5782},
        {'name':'ReservesAndSurplusExcludingRevaluationReserve','context':'OneD','value':153.0175},
        {'name':'PolicyholdersLiabilitiesToShareholdersFund','context':'OneD','value':900.0},
    ]
    nw,mode=ia.networth_from(fs)
    assert mode=='direct_shareholders_funds'
    assert nw['value']==177.4954


def test_bank_networth_uses_capital_plus_reserves_onei():
    fs=[
        {'name':'Capital','context':'OneI','value':6.2},
        {'name':'ReservesAndSurplus','context':'OneI','value':2129.5},
        {'name':'CapitalAndLiabilities','context':'OneI','value':19460.0},
    ]
    nw,mode=ia.networth_from(fs)
    assert mode=='bank_capital_plus_reserves'
    assert nw['value']==2135.7


def test_face_value_action_fallback_requires_agreement():
    assert ia.face_from_actions([{'faceVal':'10'},{'faceVal':10.0}])['value']==10.0
    assert ia.face_from_actions([{'faceVal':'10'},{'faceVal':'5'}]) is None


def test_live_change_files_are_not_written_by_hardened_anchor():
    text=''.join((ROOT/'scripts'/p).read_text() for p in [
        'current_definition_integrated_anchor.py',
        'current_definition_integrated_anchor_v2.py',
        'current_definition_integrated_anchor_v3.py',
    ])
    for forbidden in ('model.js','latest.json','multiasset.py'):
        assert forbidden not in text
