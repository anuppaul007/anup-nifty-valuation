from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import current_definition_anchor_validation as legacy
import current_definition_integrated_anchor as ia


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


def test_yield_aggregation_identity():
    rows=[{'weight':0.6,'earnings_yield':0.05,'book_yield':0.25,'dividend_yield_pct':1.0},
          {'weight':0.4,'earnings_yield':0.10,'book_yield':0.50,'dividend_yield_pct':2.0}]
    pe=1/sum(r['weight']*r['earnings_yield'] for r in rows)
    pb=1/sum(r['weight']*r['book_yield'] for r in rows)
    dy=sum(r['weight']*r['dividend_yield_pct'] for r in rows)
    assert round(pe,8)==round(1/0.07,8)
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


def test_future_filing_is_rejected_point_in_time():
    rows=[_row('30-JUN-2026','Consolidated','2026-09-01')]
    chosen,basis=ia.choose_quarter(rows,'30-JUN-2026')
    assert chosen is None and basis is None


def test_life_insurance_pat_tag_is_explicitly_supported():
    fs=[{'name':'ProfitLossAfterTaxAndExtraordinaryItems','context':'OneD','value':611.19}]
    f=ia.profit_from(fs)
    assert f['value']==611.19


def test_life_insurance_shareholders_fund_excludes_policyholder_items():
    fs=[
        {'name':'PaidUpEquityShareCapital','context':'OneI','value':20.0},
        {'name':'ReservesAndSurplusExcludingRevaluationReserve','context':'OneD','value':170.0},
        {'name':'FairValueChangeAccountAndRevaluationReserveShareholders','context':'OneI','value':5.0},
        {'name':'PolicyholdersLiabilitiesToShareholdersFund','context':'OneD','value':900.0},
        {'name':'InvestmentsShareholdersFund','context':'OneI','value':800.0},
    ]
    nw,mode=ia.networth_from(fs)
    assert mode=='insurance_shareholders_fund'
    assert nw['value']==195.0


def test_face_value_action_fallback_requires_agreement():
    assert ia.face_from_actions([{'faceVal':'10'},{'faceVal':10.0}])['value']==10.0
    assert ia.face_from_actions([{'faceVal':'10'},{'faceVal':'5'}]) is None


def test_live_change_flags_are_not_part_of_reconstruction_logic():
    # Guard the research contract at source level: the module contains no write
    # target for live model/data packets.
    text=(ROOT/'scripts'/'current_definition_integrated_anchor.py').read_text()
    for forbidden in ('model.js','latest.json','multiasset.py'):
        assert forbidden not in text
