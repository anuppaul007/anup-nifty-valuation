from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import gsec_timing_audit as g


def _built():
    screen = g.load_screen()
    variants, integrity = g.build_variants(screen)
    return screen, variants, integrity


def test_incumbent_recomputes_to_machine_precision():
    _, _, integrity = _built()
    assert integrity["max_abs_incumbent_recompute_z_diff"] < 1e-12
    assert integrity["max_abs_incumbent_recompute_equity_diff_pp"] < 1e-10


def test_rbi_timing_uses_latest_prior_month_end_for_jan_2000():
    _, variants, _ = _built()
    r = variants["rbi_timing_corrected"][0]
    assert r["signal_date"] == "2000-01-01"
    assert r["gsec_asof"] == "1999-12-31"
    assert abs(r["gsec10"] - 11.2471) < 1e-12
    assert r["timing_changed"] is True


def test_safe_variant_does_not_advance_oecd_rows():
    _, variants, _ = _built()
    base = variants["incumbent"]
    safe = variants["rbi_timing_corrected"]
    checked = 0
    for a, b in zip(base, safe):
        if not g.is_rbi_record(a):
            checked += 1
            assert b["gsec_asof"] == a["gsec_asof"]
            assert b["gsec10"] == a["gsec10"]
    assert checked > 0


def test_all_challenger_observations_are_strictly_before_signal():
    _, variants, _ = _built()
    for name in ("rbi_timing_corrected", "observation_date_only"):
        for r in variants[name]:
            assert pd.Timestamp(r["gsec_asof"]) < pd.Timestamp(r["signal_date"])


def test_safe_changes_are_confined_to_rbi_rows():
    _, variants, _ = _built()
    for a, b in zip(variants["incumbent"], variants["rbi_timing_corrected"]):
        if a["gsec_asof"] != b["gsec_asof"]:
            assert g.is_rbi_record(a)


def test_threshold_bucket_is_strict():
    assert g.bucket(80.0001) == "equity_gt_80"
    assert g.bucket(80.0) == "middle"
    assert g.bucket(20.0) == "middle"
    assert g.bucket(19.9999) == "debt_gt_80"


def test_research_output_cannot_authorize_live_change():
    result = g.build(run_backtest=False)
    assert result["research_only"] is True
    assert result["live_model_changed"] is False
    assert result["live_allocation_changed"] is False
    assert result["backtest"] is None


def test_rbi_table_definition_is_explicitly_month_end():
    text = g.OFFICIAL_VERIFICATION["rbi_table_definition"].lower()
    assert "month-end yield" in text
    assert "government dated securities" in text
