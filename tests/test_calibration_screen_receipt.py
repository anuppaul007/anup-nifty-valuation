"""Synthetic end-to-end calibration entrypoint and stale-screen replay checks.

All data are generated in a temporary directory. No holdout or returns.
"""
import hashlib
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import calibration_anchor_guard as guard
import calibration_stability_audit as audit


class SyntheticCalibrationEntrypoint(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.screen = self.root / "data/monthly_signal_screen.json"
        self.latest_path = self.root / "data/latest.json"
        self.reliability_path = self.root / "data/reliability_audit.json"
        self.output = self.root / "data/calibration_stability_audit.json"
        self.model = self.root / "model.js"
        self.version = "synthetic-v"
        required = [
            "peM:22.44", "peS:2.08", "pbM:3.54",
            "roeM:16.15402934929392", "dyM:1.25", "dyS:.18",
            "gapM:-2.60", "gapS:.70", "k:1.35", "zc:2.5",
            "earnMax:6", "trendRiskOffPP:20",
            "offset:0.0031695843111495", "scale:0.062405429030436874"
        ]
        self.model.write_text("const VERSION='synthetic-v';\n// " + " ".join(required))
        for rel in guard.RELIABILITY_SOURCE_PATHS:
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_text("synthetic input: " + rel)
        self.rows = [
            {"signal_date": f"2023-{i//12+1:02d}-{i%12+1:02d}",
             "methodology_era": "Current ratio definitions",
             "pe": 18 + i*.11, "pb": 2.5 + i*.035,
             "dy": 1 + i*.018, "gsec10": 6 + i*.025}
            for i in range(36)
        ]
        self.screen.write_text(json.dumps({"records": self.rows, "yield_rule": "synthetic"}))
        self.latest = {
            "model_version": self.version,
            "generated_at": "2026-10-20T12:00:00+00:00",
            "nifty": {"date": "2026-10-20", "level": 20000,
                      "pe": 22, "pb": 3.5, "div_yield": 1.25,
                      "gsec10": 6.5, "gsec_meta": {"asof": "2026-10-19"}},
            "earnings": {"score": 0}, "trend": {"risk_off": False}
        }
        self.latest_path.write_text(json.dumps(self.latest))
        current = audit.raw_vector(22, 3.5, 1.25, 6.5)
        center, scale = audit.production_centers_scales()
        equity = audit.allocation(audit.z_from(current, center, scale), 0, False)["policy_equity_pct"]
        self.reliability = {
            "schema_version": 1, "status": "structural_checks_passed",
            "allocation_ready_at_capture": True, "hold_reason": None,
            "model_version": self.version, "evaluated_at": self.latest["generated_at"],
            "current_formula_comparison": {"new_policy_equity_pct": equity},
            "source_hashes": {
                p: hashlib.sha256((self.root / p).read_bytes()).hexdigest()
                for p in guard.RELIABILITY_SOURCE_PATHS
            }
        }
        self.save_reliability()

    def save_reliability(self):
        self.reliability_path.write_text(json.dumps(self.reliability, allow_nan=True))

    def run_entrypoint(self):
        with patch.multiple(audit, ROOT=self.root, SCREEN=self.screen,
                            LATEST=self.latest_path, RELIABILITY=self.reliability_path,
                            MODEL=self.model, OUT=self.output):
            audit.main()
        return json.loads(self.output.read_text())

    def verify(self):
        return guard.verify_publication(
            self.output, root=self.root, latest=self.latest,
            reliability=self.reliability, model_version=self.version,
            screen=self.screen)

    def test_nested_and_nonfinite_inputs_withhold_without_uncaught_exceptions(self):
        # Independent review flagged nested structures and NaN bypassing
        # top-level checks. Run actual audit.main with synthetic input files.
        baseline_screen = {"records": self.rows, "yield_rule": "synthetic"}
        baseline_latest = self.latest
        cases = (
            ("nondict_screen_row", "invalid_calibration_input_structure"),
            ("missing_nifty", "invalid_calibration_input_structure"),
            ("null_nifty", "invalid_calibration_input_structure"),
            ("nondict_earnings", "invalid_calibration_input_structure"),
            ("nondict_trend", "invalid_calibration_input_structure"),
            ("screen_nan_pe", "invalid_calibration_input_values"),
            ("screen_inf_yield", "invalid_calibration_input_values"),
            ("latest_nan_pe", "invalid_calibration_input_values"),
            ("latest_inf_yield", "invalid_calibration_input_values"),
            ("missing_gsec_meta", "invalid_calibration_input_values"),
            ("nan_earnings_score", "invalid_calibration_input_values"),
            ("string_risk_off", "invalid_calibration_input_values"),
            ("nan_market_level", "invalid_calibration_input_values"),
            ("missing_signal_date", "invalid_calibration_input_values"),
            ("short_screen", "invalid_current_definition_count"),
            ("wrong_latest_model", "latest_model_version_mismatch"),
        )
        for label, expected_reason in cases:
            with self.subTest(label=label):
                screen = json.loads(json.dumps(baseline_screen))
                latest = json.loads(json.dumps(baseline_latest))
                if label == "nondict_screen_row":
                    screen["records"][0] = "not-a-row"
                elif label == "missing_nifty":
                    latest.pop("nifty")
                elif label == "null_nifty":
                    latest["nifty"] = None
                elif label == "nondict_earnings":
                    latest["earnings"] = []
                elif label == "nondict_trend":
                    latest["trend"] = "bad"
                elif label == "screen_nan_pe":
                    screen["records"][0]["pe"] = float("nan")
                elif label == "screen_inf_yield":
                    screen["records"][0]["gsec10"] = float("inf")
                elif label == "latest_nan_pe":
                    latest["nifty"]["pe"] = float("nan")
                elif label == "latest_inf_yield":
                    latest["nifty"]["gsec10"] = float("inf")
                elif label == "missing_gsec_meta":
                    latest["nifty"].pop("gsec_meta")
                elif label == "nan_earnings_score":
                    latest["earnings"]["score"] = float("nan")
                elif label == "string_risk_off":
                    latest["trend"]["risk_off"] = "false"
                elif label == "nan_market_level":
                    latest["nifty"]["level"] = float("nan")
                elif label == "missing_signal_date":
                    screen["records"][0].pop("signal_date")
                elif label == "short_screen":
                    screen["records"].pop()
                elif label == "wrong_latest_model":
                    latest["model_version"] = "different-v"
                self.screen.write_text(json.dumps(screen))
                self.latest_path.write_text(json.dumps(latest))
                report = self.run_entrypoint()
                self.assertEqual(report["publication_status"], "withheld")
                self.assertEqual(report["withheld_reason"], expected_reason)
                self.assertEqual(report["variants"], [])
                self.assertIsNone(report["production_reproduction"])
                with self.assertRaisesRegex(SystemExit, "calibration_publication_blocked"):
                    guard.verify_publication(self.output)
        self.screen.write_text(json.dumps(baseline_screen))
        self.latest_path.write_text(json.dumps(baseline_latest))

    def test_real_entrypoint_publishes_then_replay_fails_on_screen_mutation(self):
        published = self.run_entrypoint()
        self.assertEqual(published["publication_status"], "published")
        self.assertEqual(len(published["variants"]), 9)
        self.assertEqual(published["calibration_screen_sha256"], guard.screen_receipt(self.screen))
        self.verify()
        # Preserve all numerical anchor and reliability-source bytes; alter only screen.
        self.rows[0]["pe"] += 0.4
        self.screen.write_text(json.dumps({"records": self.rows, "yield_rule": "synthetic"}))
        with self.assertRaisesRegex(SystemExit, "stale_calibration_screen"):
            self.verify()
        # A fresh recomputation must generate a new bound receipt.
        renewed = self.run_entrypoint()
        self.assertNotEqual(published["calibration_screen_sha256"], renewed["calibration_screen_sha256"])
        self.verify()

    def test_missing_null_invalid_nonfinite_and_mismatched_anchors_fail_closed(self):
        cases = [
            ("missing", object(), "missing_anchor"),
            ("null", None, "null_anchor"),
            ("bool", True, "invalid_anchor_type"),
            ("string", "40", "invalid_anchor_type"),
            ("nan", float("nan"), "nonfinite_anchor"),
            ("inf", float("inf"), "nonfinite_anchor"),
            ("out_of_range", 101, "out_of_range_anchor"),
            ("mismatch", 99.0, "production_reproduction_mismatch"),
        ]
        valid = self.reliability["current_formula_comparison"]["new_policy_equity_pct"]
        for label, value, reason in cases:
            with self.subTest(label=label):
                if label == "missing":
                    self.reliability["current_formula_comparison"] = {}
                else:
                    self.reliability["current_formula_comparison"] = {"new_policy_equity_pct": value}
                self.save_reliability()
                if label == "mismatch":
                    with self.assertRaisesRegex(RuntimeError, reason):
                        self.run_entrypoint()
                    report = json.loads(self.output.read_text())
                else:
                    report = self.run_entrypoint()
                self.assertEqual(report["publication_status"], "withheld")
                self.assertEqual(report["withheld_reason"], reason)
                self.assertEqual(report["variants"], [])
                with self.assertRaisesRegex(SystemExit, "calibration_publication_blocked"):
                    self.verify()
        self.reliability["current_formula_comparison"] = {"new_policy_equity_pct": valid}

    def test_stale_hash_and_vintage_withhold_without_false_green(self):
        for label in ("hash", "vintage"):
            with self.subTest(label=label):
                if label == "hash":
                    self.reliability["source_hashes"]["model.js"] = "0" * 64
                else:
                    self.reliability["evaluated_at"] = "2026-10-19T12:00:00+00:00"
                self.save_reliability()
                report = self.run_entrypoint()
                self.assertEqual(report["publication_status"], "withheld")
                self.assertEqual(report["withheld_reason"],
                                 "stale_source_hash" if label == "hash" else "stale_reliability_vintage")
                with self.assertRaisesRegex(SystemExit, "calibration_publication_blocked"):
                    self.verify()
                self.reliability["source_hashes"]["model.js"] = hashlib.sha256(self.model.read_bytes()).hexdigest()
                self.reliability["evaluated_at"] = self.latest["generated_at"]

    def test_mutation_between_parse_and_publication_cannot_rebind_old_variants(self):
        original_bytes = self.screen.read_bytes()
        original_validator = audit.validate_provenance

        def mutate_after_parse(*args, **kwargs):
            reason = original_validator(*args, **kwargs)
            self.rows[0]["pe"] += 0.6
            self.screen.write_text(json.dumps({"records": self.rows, "yield_rule": "synthetic"}))
            return reason

        with patch.object(audit, "validate_provenance", side_effect=mutate_after_parse):
            report = self.run_entrypoint()
        self.assertEqual(report["publication_status"], "published")
        self.assertEqual(report["calibration_screen_sha256"],
                         hashlib.sha256(original_bytes).hexdigest())
        self.assertNotEqual(report["calibration_screen_sha256"], guard.screen_receipt(self.screen))
        with self.assertRaisesRegex(SystemExit, "stale_calibration_screen"):
            self.verify()

    def test_published_packet_tamper_or_partial_replay_is_blocked(self):
        # A current reliability hash and timestamp must not bless stale or
        # altered consumer-facing fields in a schema-2 research artifact.
        original = self.run_entrypoint()
        self.verify()
        for label, mutation in (
            ("price", lambda p: p.update({"pe": p["pe"] + 0.1})),
            ("date", lambda p: p.update({"nifty_date": "2026-10-19"})),
            ("yield_vintage", lambda p: p.update({"gsec_asof": "2026-10-01"})),
            ("missing_field", lambda p: p.pop("level")),
            ("extra_field", lambda p: p.update({"unverified": True})),
        ):
            with self.subTest(label=label):
                altered = json.loads(json.dumps(original))
                mutation(altered["current_packet"])
                self.output.write_text(json.dumps(altered))
                with self.assertRaisesRegex(SystemExit, "stale_report_packet"):
                    self.verify()
        for malformed in (None, [], "replayed"):
            with self.subTest(malformed=repr(malformed)):
                altered = json.loads(json.dumps(original))
                altered["current_packet"] = malformed
                self.output.write_text(json.dumps(altered))
                with self.assertRaisesRegex(SystemExit, "stale_report_packet"):
                    self.verify()
        self.output.write_text(json.dumps(original))
        self.verify()

    def test_recomputed_publication_rejects_tampered_sensitivity_payload(self):
        # A correct numeric anchor and exact source receipts do not by
        # themselves prove that all nine research variants were calculated
        # from those bytes. Exercise the real deterministic publication gate.
        original = self.run_entrypoint()
        self.verify()
        with patch.multiple(audit, ROOT=self.root, SCREEN=self.screen,
                            LATEST=self.latest_path, RELIABILITY=self.reliability_path,
                            MODEL=self.model, OUT=self.output):
            audit.verify_recomputed_payload(original)
            for label, mutate in (
                ("variant", lambda p: p["variants"][0].update({
                    "policy_equity_pct": p["variants"][0]["policy_equity_pct"] + 0.75})),
                ("lens_summary", lambda p: p["one_lens_at_a_time_leave_block_sensitivity"]["pe"].update({
                    "max_abs_change_pp": 999.0})),
                ("sample", lambda p: p["sample"].update({"months": 35})),
            ):
                with self.subTest(label=label):
                    forged = json.loads(json.dumps(original))
                    mutate(forged)
                    # This negative proves the *recomputation* gate detects
                    # altered schema-2 consumer fields, not just anchor hashes.
                    with self.assertRaisesRegex(SystemExit, "recalculated_payload_mismatch"):
                        audit.verify_recomputed_payload(forged)
            # A genuine deterministic artifact remains accepted.
            audit.verify_recomputed_payload(original)

    def test_publication_vintage_spoofing_fails_even_with_valid_numeric_receipts(self):
        # The recomputation gate excludes generated_at because it is a
        # nondeterministic clock. The entrypoint's actual publication verifier
        # must independently reject fabricated vintage metadata.
        original = self.run_entrypoint()
        self.verify()
        cases = (
            ("missing", None, "invalid_publication_vintage"),
            ("null", False, "invalid_publication_vintage"),
            ("malformed", "not-a-date", "invalid_publication_vintage"),
            ("naive", "2026-10-21T12:00:00", "invalid_publication_vintage"),
            ("before_source", "2026-10-20T11:59:59+00:00", "stale_publication_vintage"),
            ("future", "2099-01-01T00:00:00+00:00", "future_publication_vintage"),
        )
        for label, stamp, reason in cases:
            with self.subTest(label=label):
                tampered = json.loads(json.dumps(original))
                if stamp is None:
                    tampered.pop("generated_at")
                else:
                    tampered["generated_at"] = stamp
                self.output.write_text(json.dumps(tampered))
                with self.assertRaisesRegex(SystemExit, reason):
                    self.verify()
        self.output.write_text(json.dumps(original))
        self.verify()

    def test_missing_screen_context_and_missing_file_are_blocked(self):
        self.run_entrypoint()
        with self.assertRaisesRegex(SystemExit, "provenance context missing"):
            guard.verify_publication(
                self.output, root=self.root, latest=self.latest,
                reliability=self.reliability, model_version=self.version)
        self.screen.unlink()
        with self.assertRaisesRegex(SystemExit, "unavailable_calibration_screen"):
            self.verify()


    def test_missing_corrupt_or_undecodable_reliability_file_is_explicitly_withheld(self):
        for label in ("missing", "malformed_json", "invalid_utf8"):
            with self.subTest(label=label):
                self.save_reliability()
                if label == "missing":
                    self.reliability_path.unlink()
                elif label == "malformed_json":
                    self.reliability_path.write_text("{broken json", encoding="utf-8")
                else:
                    self.reliability_path.write_bytes(bytes([255]))
                report = self.run_entrypoint()
                self.assertEqual(report["publication_status"], "withheld")
                self.assertEqual(report["withheld_reason"], "unavailable_or_invalid_reliability_document")
                self.assertEqual(report["variants"], [])
                self.assertIsNone(report["production_reproduction"])
                with self.assertRaisesRegex(SystemExit, "calibration_publication_blocked"):
                    guard.verify_publication(self.output)
        self.save_reliability()


    def test_missing_corrupt_or_structurally_invalid_screen_and_latest_are_withheld(self):
        # Only synthetic fixtures; each failure must leave an explicit rejected artifact.
        fixtures = (
            ("screen_missing", self.screen, None, "unavailable_or_invalid_calibration_input"),
            ("screen_bad_json", self.screen, b"{broken", "unavailable_or_invalid_calibration_input"),
            ("screen_bad_utf8", self.screen, bytes([255]), "unavailable_or_invalid_calibration_input"),
            ("screen_wrong_shape", self.screen, b"[]", "invalid_calibration_input_structure"),
            ("screen_missing_records", self.screen, b"{}", "invalid_calibration_input_structure"),
            ("latest_missing", self.latest_path, None, "unavailable_or_invalid_calibration_input"),
            ("latest_bad_json", self.latest_path, b"{broken", "unavailable_or_invalid_calibration_input"),
            ("latest_bad_utf8", self.latest_path, bytes([255]), "unavailable_or_invalid_calibration_input"),
            ("latest_wrong_shape", self.latest_path, b"[]", "invalid_calibration_input_structure"),
        )
        original_screen = self.screen.read_bytes()
        original_latest = self.latest_path.read_bytes()
        for label, target, corrupted, expected_reason in fixtures:
            with self.subTest(label=label):
                self.screen.write_bytes(original_screen)
                self.latest_path.write_bytes(original_latest)
                if corrupted is None:
                    target.unlink()
                else:
                    target.write_bytes(corrupted)
                report = self.run_entrypoint()
                self.assertEqual(report["publication_status"], "withheld")
                self.assertEqual(report["withheld_reason"], expected_reason)
                self.assertEqual(report["variants"], [])
                self.assertIsNone(report["production_reproduction"])
                with self.assertRaisesRegex(SystemExit, "calibration_publication_blocked"):
                    guard.verify_publication(self.output)
        self.screen.write_bytes(original_screen)
        self.latest_path.write_bytes(original_latest)


    def test_real_entrypoint_rejects_hash_schema_and_reliability_state_mutations(self):
        # Exercise actual audit.main(), not just validate_provenance() helpers.
        # Every case keeps the numerical equity anchor unchanged and must
        # produce an explicit withheld artifact with no research variants.
        baseline = json.loads(json.dumps(self.reliability))
        source = self.root / "trend_policy_v1.json"
        original_source = source.read_bytes()
        cases = (
            ("missing_hashes", "missing_or_extra_source_hash"),
            ("null_hashes", "missing_or_extra_source_hash"),
            ("extra_hash", "missing_or_extra_source_hash"),
            ("invalid_hash", "invalid_source_hash"),
            ("stale_hash", "stale_source_hash"),
            ("missing_source", "unavailable_source_file"),
            ("wrong_reliability_schema", "invalid_reliability_schema"),
            ("unverified_status", "unverified_reliability_status"),
            ("allocation_hold", "allocation_not_ready_at_capture"),
            ("hold_reason", "reliability_hold_reason"),
            ("wrong_reliability_model", "model_version_mismatch"),
            ("stale_evaluation_vintage", "stale_reliability_vintage"),
        )
        for label, expected_reason in cases:
            with self.subTest(label=label):
                self.reliability = json.loads(json.dumps(baseline))
                source.write_bytes(original_source)
                if label == "missing_hashes":
                    self.reliability["source_hashes"].pop("trend_policy_v1.json")
                elif label == "null_hashes":
                    self.reliability["source_hashes"] = None
                elif label == "extra_hash":
                    self.reliability["source_hashes"]["unexpected.json"] = "a" * 64
                elif label == "invalid_hash":
                    self.reliability["source_hashes"]["trend_policy_v1.json"] = "not-a-sha256"
                elif label == "stale_hash":
                    self.reliability["source_hashes"]["trend_policy_v1.json"] = "0" * 64
                elif label == "missing_source":
                    source.unlink()
                elif label == "wrong_reliability_schema":
                    self.reliability["schema_version"] = 2
                elif label == "unverified_status":
                    self.reliability["status"] = "withheld"
                elif label == "allocation_hold":
                    self.reliability["allocation_ready_at_capture"] = False
                elif label == "hold_reason":
                    self.reliability["hold_reason"] = "synthetic_missing_yield"
                elif label == "wrong_reliability_model":
                    self.reliability["model_version"] = "different-v"
                elif label == "stale_evaluation_vintage":
                    self.reliability["evaluated_at"] = "2026-10-19T12:00:00+00:00"
                self.save_reliability()
                report = self.run_entrypoint()
                self.assertEqual(report["publication_status"], "withheld")
                self.assertEqual(report["withheld_reason"], expected_reason)
                self.assertEqual(report["variants"], [])
                self.assertIsNone(report["production_reproduction"])
                with self.assertRaisesRegex(SystemExit, "calibration_publication_blocked"):
                    guard.verify_publication(self.output)
        source.write_bytes(original_source)
        self.reliability = baseline
        self.save_reliability()


    def test_finite_market_values_that_overflow_derived_lenses_withhold(self):
        # Finite JSON inputs can overflow the derived ROE/log-profitability
        # calculation. Never emit NaN/Inf sensitivity variants or crash before
        # writing a fail-closed research artifact.
        original_screen = self.screen.read_bytes()
        original_latest = self.latest_path.read_bytes()
        try:
            for label in ("screen_derived_overflow", "latest_derived_overflow"):
                with self.subTest(label=label):
                    screen = {"records": json.loads(original_screen)["records"],
                              "yield_rule": "synthetic"}
                    latest = json.loads(original_latest)
                    if label == "screen_derived_overflow":
                        screen["records"][0]["pe"] = 1e-300
                        screen["records"][0]["pb"] = 1e300
                    else:
                        latest["nifty"]["pe"] = 1e-300
                        latest["nifty"]["pb"] = 1e300
                    self.screen.write_text(json.dumps(screen))
                    self.latest_path.write_text(json.dumps(latest))
                    report = self.run_entrypoint()
                    self.assertEqual(report["publication_status"], "withheld")
                    self.assertEqual(report["withheld_reason"], "invalid_calibration_input_values")
                    self.assertEqual(report["variants"], [])
                    self.assertIsNone(report["production_reproduction"])
                    with self.assertRaisesRegex(SystemExit, "calibration_publication_blocked"):
                        guard.verify_publication(self.output)
        finally:
            self.screen.write_bytes(original_screen)
            self.latest_path.write_bytes(original_latest)


if __name__ == "__main__":
    unittest.main()
