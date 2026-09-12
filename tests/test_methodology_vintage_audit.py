from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import methodology_vintage_audit as m


def test_era_boundaries():
    assert m.era_for_date("2021-03-30") == "era_A_legacy_all"
    assert m.era_for_date("2021-03-31") == "era_B_pe_dy_current_pb_legacy"
    assert m.era_for_date("2023-09-28") == "era_B_pe_dy_current_pb_legacy"
    assert m.era_for_date("2023-09-29") == "era_C_current_all"


def test_official_breaks_include_pe_dy_and_pb():
    assert m.BREAKS[0]["changed_fields"] == ["pe", "dy"]
    assert m.BREAKS[1]["changed_fields"] == ["pb"]
    assert m.BREAKS[0]["effective_date"] == "2021-03-31"
    assert m.BREAKS[1]["effective_date"] == "2023-09-29"


def test_price_adjusted_pe_factor_removes_price_move():
    before = {"pe": 20.0, "pb": 3.0, "dy": 1.0}
    after = {"pe": 22.0, "pb": 3.3, "dy": 1.0 / 1.1}
    pr = 1.1
    assert abs(m.price_adjusted_method_factor("pe", before, after, pr) - 1.0) < 1e-12
    assert abs(m.price_adjusted_method_factor("pb", before, after, pr) - 1.0) < 1e-12
    assert abs(m.price_adjusted_method_factor("dy", before, after, pr) - 1.0) < 1e-12


def test_vintage_matrix_does_not_claim_full_history():
    india = m.VINTAGE_MATRIX["india_10y_oecd"]
    assert india["observation_start"] == "2011-12"
    assert india["alfred_revision_history_start"] == "2018-07-17"
    assert india["status"] == "partial_vintage_archive"


def test_recompute_returns_bounded_equity():
    p = {
        "peM": 22.44, "peS": 2.08, "pbM": 3.88, "pbS": 0.45,
        "roeM": 17.36, "roeS": 1.92, "dyM": 1.25, "dyS": 0.18,
        "gapM": -2.6, "gapS": 0.7, "beta": 0.6, "k": 1.35,
        "zc": 2.5, "wPE": 30, "wPB": 25, "wGAP": 30, "wDY": 10,
    }
    out = m.recompute(20.0, 3.0, 1.2, 7.0, p)
    assert 0.0 <= out["core_equity"] <= 100.0
    assert set(out["lenses"]) == {"pe", "pb_profitability_adjusted", "gap", "dy"}


def test_summarize_eras_separates_regimes():
    rows = [
        {"nifty_asof":"2021-03-30","signal_date":"2021-03-31","pe":20,"pb":3,"dy":1,"z":0,"core_equity":50},
        {"nifty_asof":"2021-03-31","signal_date":"2021-04-01","pe":18,"pb":3,"dy":1,"z":-1,"core_equity":80},
        {"nifty_asof":"2023-09-29","signal_date":"2023-10-01","pe":20,"pb":2.8,"dy":1.2,"z":0.2,"core_equity":45},
    ]
    out = m.summarize_eras(rows)
    assert out["era_A_legacy_all"]["months"] == 1
    assert out["era_B_pe_dy_current_pb_legacy"]["months"] == 1
    assert out["era_C_current_all"]["months"] == 1


def test_current_era_is_only_fully_current_ratio_definition():
    assert m.ERA_DEFS["era_C_current_all"]["ratio_basis"] == {
        "pe": "consolidated", "pb": "consolidated", "dy": "rolling-12m ex-dividend"
    }


def test_long_history_governance_is_research_only_by_design():
    assert "partial_vintage_archive" == m.VINTAGE_MATRIX["india_10y_oecd"]["status"]
    assert "standalone" in m.ERA_DEFS["era_A_legacy_all"]["ratio_basis"]["pe"]
