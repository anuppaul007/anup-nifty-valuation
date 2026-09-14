from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("inv", SCRIPTS / "development_xbrl_tag_inventory.py")
inv = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inv)


def test_candidate_family_normalisation():
    assert "profit" in inv._candidate_family("ProfitLossAttributableToOwnersOfParent")
    assert "net_worth_or_equity" in inv._candidate_family("EquityAttributableToOwnersOfParent")
    assert "bank_equity_structure" in inv._candidate_family("Capital")
    assert "bank_equity_structure" in inv._candidate_family("ReservesAndSurplus")
    assert "share_capital" in inv._candidate_family("PaidUpEquityShareCapital")
    assert "face_value" in inv._candidate_family("FaceValueOfEquityShareCapital")


def test_template_family_uses_specific_filename_family_before_generic_indas():
    assert inv._template_family("https://nsearchives.nseindia.com/corporate/xbrl/BANKING_123.xml") == "BANKING"
    assert inv._template_family("https://nsearchives.nseindia.com/corporate/xbrl/INDAS_123.xml") == "INDAS"
    assert inv._template_family("https://nsearchives.nseindia.com/corporate/xbrl/NBFC_123.xml") == "NBFC"
    assert inv._template_family("https://nsearchives.nseindia.com/corporate/xbrl/NBFC_INDAS_123.xml") == "NBFC"


def test_only_official_nse_xml_is_selected():
    assert inv._valid_xbrl_url("https://nsearchives.nseindia.com/corporate/xbrl/ABC.xml")
    assert not inv._valid_xbrl_url("https://example.com/ABC.xml")
    assert not inv._valid_xbrl_url("https://nsearchives.nseindia.com/a.pdf")
    assert not inv._valid_xbrl_url(None)


def test_synthetic_xbrl_context_and_fact_inventory():
    raw = b'''<?xml version="1.0"?>
    <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:in="http://example.com/in">
      <xbrli:context id="D1"><xbrli:entity><xbrli:identifier scheme="x">A</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2023-04-01</xbrli:startDate><xbrli:endDate>2023-06-30</xbrli:endDate></xbrli:period></xbrli:context>
      <xbrli:context id="I1"><xbrli:entity><xbrli:identifier scheme="x">A</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2023-06-30</xbrli:instant></xbrli:period></xbrli:context>
      <in:ProfitLossAttributableToOwnersOfParent contextRef="D1" unitRef="INR" decimals="0">123</in:ProfitLossAttributableToOwnersOfParent>
      <in:Capital contextRef="I1" unitRef="INR" decimals="0">20</in:Capital>
      <in:PaidUpEquityShareCapital contextRef="I1" unitRef="INR" decimals="0">10</in:PaidUpEquityShareCapital>
      <in:FaceValueOfEquityShareCapital contextRef="I1" unitRef="INR" decimals="0">1</in:FaceValueOfEquityShareCapital>
    </xbrli:xbrl>'''
    x = inv.inspect_xbrl(raw)
    assert x["contexts"] == 2
    assert x["candidate_family_counts"]["profit"] == 1
    assert x["candidate_family_counts"]["bank_equity_structure"] == 1
    assert x["candidate_family_counts"]["share_capital"] >= 1
    assert x["candidate_family_counts"]["face_value"] == 1
    assert x["candidate_facts"]["profit"][0]["context"]["end_date"] == "2023-06-30"


def test_inventory_module_has_no_ratio_formula():
    text = (ROOT / "scripts" / "development_xbrl_tag_inventory.py").read_text(encoding="utf-8")
    assert '"ratios_computed": False' in text
    assert '"holdout_target_fetch_count": 0' in text
    assert "aggregate_from_point_in_time_inputs" not in text
