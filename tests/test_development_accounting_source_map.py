from pathlib import Path
import importlib.util
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("srcmap", ROOT / "scripts" / "development_accounting_source_map.py")
src = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(src)


def rec(end, ts, consolidated="Consolidated", xbrl="https://nsearchives.nseindia.com/corporate/ixbrl/X_INDAS_Y.html"):
    return {
        "symbol": "TEST",
        "toDate": end,
        "fromDate": "01-01-2023",
        "exchdisstime": ts,
        "filingDate": ts.split(" ")[0],
        "consolidated": consolidated,
        "xbrl": xbrl,
        "seqNumber": f"{end}-{ts}-{consolidated}",
    }


def test_signal_date_from_official_header():
    text = "Constituents of NIFTY 50\n September 29, 2023\n Symbol Security Name"
    assert src.parse_signal_date(text) == "2023-09-29"


def test_public_timestamp_prefers_exchange_dissemination():
    r = {"exchdisstime": "29-Sep-2023 14:00:00", "broadCastDate": "29-Sep-2023 13:00:00", "filingDate": "29-Sep-2023"}
    ts, field = src.public_timestamp(r)
    assert field == "exchdisstime"
    assert ts == pd.Timestamp("2023-09-29 14:00:00")


def test_1530_cutoff_excludes_late_same_day_filing():
    rows = [
        rec("30-Jun-2023", "29-Sep-2023 15:29:59"),
        rec("30-Jun-2023", "29-Sep-2023 15:31:00", consolidated="Standalone"),
    ]
    chosen = src.choose_latest_by_period(rows, "2023-09-29")
    assert len(chosen) == 1
    assert chosen[0]["consolidated"] == "Consolidated"


def test_ttm_chain_prefers_consolidated_for_each_period():
    rows = []
    for end, ts in [
        ("30-Jun-2023", "20-Jul-2023 12:00:00"),
        ("31-Mar-2023", "20-Apr-2023 12:00:00"),
        ("31-Dec-2022", "20-Jan-2023 12:00:00"),
        ("30-Sep-2022", "20-Oct-2022 12:00:00"),
    ]:
        rows.append(rec(end, ts, "Standalone"))
        rows.append(rec(end, ts, "Consolidated"))
    x = src.pick_reporting_chain(rows, "2023-09-29", 4)
    assert x["complete"] is True
    assert len(x["records"]) == 4
    assert x["standalone_fallback_periods"] == []
    assert all(r["consolidated"] == "Consolidated" for r in x["records"])


def test_ttm_chain_records_standalone_fallback_not_silent_fill():
    rows = [
        rec("30-Jun-2023", "20-Jul-2023 12:00:00", "Standalone"),
        rec("31-Mar-2023", "20-Apr-2023 12:00:00"),
        rec("31-Dec-2022", "20-Jan-2023 12:00:00"),
        rec("30-Sep-2022", "20-Oct-2022 12:00:00"),
    ]
    x = src.pick_reporting_chain(rows, "2023-09-29", 4)
    assert x["complete"] is True
    assert x["standalone_fallback_periods"] == ["2023-06-30"]


def test_template_detection():
    assert src.template_from_xbrl("https://x/INTEGRATED_FILING_INDAS_123_iXBRL_WEB.html") == "INDAS"
    assert src.template_from_xbrl("https://x/INTEGRATED_FILING_LI_123_iXBRL_WEB.html") == "LI"
    assert src.template_from_xbrl(None) is None


def test_stage_b_code_has_no_holdout_target_fetch():
    text = (ROOT / "scripts" / "development_accounting_source_map.py").read_text(encoding="utf-8")
    assert "dashboard_url(" not in text
    assert '"holdout_target_fetch_count": 0' in text
    assert 'live_authority": "none"' in text
