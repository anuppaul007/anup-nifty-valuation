#!/usr/bin/env python3
"""Deterministically evaluate the frozen Institutional Readiness Score v1.

This module does not infer or tune scores. It mechanically applies the frozen
weights, critical-dimension floors and controlling promotion gates recorded in
`institutional_readiness_policy_v1.json`. Missing or malformed controlling
evidence fails closed by raising an error rather than inventing a pass.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "institutional_readiness_policy_v1.json"
DEFAULT_OUTPUT = ROOT / "data" / "institutional_readiness.json"


class ReadinessError(ValueError):
    """Raised when readiness inputs violate the frozen schema/guardrails."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReadinessError(f"cannot load valid JSON from {path}: {exc}") from exc
    if not isinstance(obj, dict):
        raise ReadinessError(f"top-level JSON must be an object: {path}")
    return obj


def _decimal(value: Any, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReadinessError(f"{label} must be a finite number")
    number = Decimal(str(value))
    if not number.is_finite():
        raise ReadinessError(f"{label} must be finite")
    return number


def _require_bool(obj: dict[str, Any], key: str, label: str) -> bool:
    if key not in obj or not isinstance(obj[key], bool):
        raise ReadinessError(f"{label}.{key} must be an explicit boolean")
    return obj[key]


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("schema_version") != 1:
        raise ReadinessError("unsupported readiness policy schema_version")
    if policy.get("policy_id") != "institutional-readiness-score-v1":
        raise ReadinessError("unexpected readiness policy_id")
    if policy.get("score_is_probability") is not False:
        raise ReadinessError("score_is_probability must remain false")
    if policy.get("research_only") is not True:
        raise ReadinessError("readiness score must remain research/governance only")
    if policy.get("live_authority") != "none":
        raise ReadinessError("readiness policy must have zero live authority")
    if policy.get("live_model_changed") is not False:
        raise ReadinessError("readiness policy may not claim a live model change")
    if policy.get("live_allocation_changed") is not False:
        raise ReadinessError("readiness policy may not claim a live allocation change")

    admission = policy.get("admission_rule")
    if not isinstance(admission, dict):
        raise ReadinessError("admission_rule must be an object")
    overall_min = _decimal(admission.get("overall_score_min"), "admission_rule.overall_score_min")
    critical_min = _decimal(
        admission.get("critical_dimension_score_min"),
        "admission_rule.critical_dimension_score_min",
    )
    if overall_min != Decimal("90.0"):
        raise ReadinessError("overall CIO admission threshold is frozen at 90")
    if critical_min != Decimal("80.0"):
        raise ReadinessError("critical-dimension CIO admission threshold is frozen at 80")
    if admission.get("require_all_controlling_gates_pass") is not True:
        raise ReadinessError("all controlling gates must be required")
    if admission.get("require_material_model_risk_clearance") is not True:
        raise ReadinessError("material model-risk clearance must be required")

    evidence = policy.get("controlling_evidence")
    if not isinstance(evidence, dict):
        raise ReadinessError("controlling_evidence must be an object")
    source = evidence.get("robust_evaluation_summary")
    if not isinstance(source, str) or not source:
        raise ReadinessError("controlling robust-evaluation source must be explicit")
    expected_decision = evidence.get("eligible_promotion_decision")
    if not isinstance(expected_decision, str) or not expected_decision:
        raise ReadinessError("eligible promotion decision must be explicit")
    gate_keys = evidence.get("required_gate_keys")
    if (
        not isinstance(gate_keys, list)
        or not gate_keys
        or any(not isinstance(key, str) or not key for key in gate_keys)
        or len(gate_keys) != len(set(gate_keys))
    ):
        raise ReadinessError("required_gate_keys must be a non-empty unique string list")

    dimensions = policy.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        raise ReadinessError("dimensions must be a non-empty list")
    seen: set[str] = set()
    total_weight = Decimal("0")
    critical_count = 0
    for idx, dimension in enumerate(dimensions):
        if not isinstance(dimension, dict):
            raise ReadinessError(f"dimensions[{idx}] must be an object")
        dim_id = dimension.get("id")
        if not isinstance(dim_id, str) or not dim_id or dim_id in seen:
            raise ReadinessError(f"dimensions[{idx}].id must be unique and non-empty")
        seen.add(dim_id)
        if not isinstance(dimension.get("name"), str) or not dimension["name"]:
            raise ReadinessError(f"dimensions[{idx}].name must be non-empty")
        weight = _decimal(dimension.get("weight_pct"), f"dimensions[{idx}].weight_pct")
        score = _decimal(dimension.get("score"), f"dimensions[{idx}].score")
        if weight <= 0 or weight > 100:
            raise ReadinessError(f"dimensions[{idx}].weight_pct out of range")
        if score < 0 or score > 100:
            raise ReadinessError(f"dimensions[{idx}].score out of range")
        if not isinstance(dimension.get("critical"), bool):
            raise ReadinessError(f"dimensions[{idx}].critical must be boolean")
        if dimension["critical"]:
            critical_count += 1
        total_weight += weight
    if total_weight != Decimal("100.0"):
        raise ReadinessError(f"dimension weights must sum exactly to 100, got {total_weight}")
    if critical_count == 0:
        raise ReadinessError("at least one dimension must be critical")

    clearance = policy.get("material_model_risk_clearance")
    if not isinstance(clearance, dict):
        raise ReadinessError("material_model_risk_clearance must be an object")
    _require_bool(clearance, "cleared", "material_model_risk_clearance")
    if not isinstance(clearance.get("reason"), str) or not clearance["reason"]:
        raise ReadinessError("material model-risk clearance reason must be explicit")


def compute_status(policy: dict[str, Any], robust: dict[str, Any]) -> dict[str, Any]:
    validate_policy(policy)
    if robust.get("schema_version") != 1:
        raise ReadinessError("unsupported robust-evaluation schema_version")
    decision = robust.get("decision")
    if not isinstance(decision, str) or not decision:
        raise ReadinessError("robust-evaluation decision must be explicit")

    admission = policy["admission_rule"]
    overall_min = _decimal(admission["overall_score_min"], "overall_score_min")
    critical_min = _decimal(admission["critical_dimension_score_min"], "critical_min")

    dimension_rows: list[dict[str, Any]] = []
    weighted_total = Decimal("0")
    failed_critical: list[dict[str, Any]] = []
    critical_scores: list[Decimal] = []
    for dimension in policy["dimensions"]:
        weight = _decimal(dimension["weight_pct"], f"{dimension['id']}.weight_pct")
        score = _decimal(dimension["score"], f"{dimension['id']}.score")
        weighted = weight * score / Decimal("100")
        weighted_total += weighted
        row = {
            "id": dimension["id"],
            "name": dimension["name"],
            "weight_pct": float(weight),
            "critical": dimension["critical"],
            "score": float(score),
            "weighted_points": float(weighted.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        }
        dimension_rows.append(row)
        if dimension["critical"]:
            critical_scores.append(score)
            if score < critical_min:
                failed_critical.append({"id": dimension["id"], "score": float(score)})

    score_exact = weighted_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    score_rounded = weighted_total.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    overall_pass = weighted_total >= overall_min
    critical_pass = not failed_critical

    evidence = policy["controlling_evidence"]
    gate_matrix = robust.get("gate_matrix")
    if not isinstance(gate_matrix, dict):
        raise ReadinessError("robust-evaluation gate_matrix must be an object")
    observed_gates: dict[str, bool] = {}
    failed_gate_keys: list[str] = []
    for key in evidence["required_gate_keys"]:
        value = _require_bool(gate_matrix, key, "gate_matrix")
        observed_gates[key] = value
        if not value:
            failed_gate_keys.append(key)

    expected_decision = evidence["eligible_promotion_decision"]
    promotion_decision_pass = decision == expected_decision
    all_controlling_gates_pass = not failed_gate_keys and promotion_decision_pass

    clearance = policy["material_model_risk_clearance"]
    model_risk_cleared = _require_bool(
        clearance, "cleared", "material_model_risk_clearance"
    )
    eligible = (
        overall_pass
        and critical_pass
        and all_controlling_gates_pass
        and model_risk_cleared
    )

    return {
        "schema_version": 1,
        "policy_id": policy["policy_id"],
        "generated_from": {
            "policy": "institutional_readiness_policy_v1.json",
            "robust_evaluation_summary": evidence["robust_evaluation_summary"],
        },
        "source_robust_evaluation_decision": decision,
        "score": {
            "exact": float(score_exact),
            "rounded_1dp": float(score_rounded),
            "minimum_required": float(overall_min),
            "threshold_pass": overall_pass,
        },
        "critical_dimensions": {
            "minimum_required": float(critical_min),
            "minimum_observed": float(min(critical_scores)),
            "failed": failed_critical,
            "threshold_pass": critical_pass,
        },
        "controlling_gates": {
            "required_gate_keys": list(evidence["required_gate_keys"]),
            "observed": observed_gates,
            "failed_gate_keys": failed_gate_keys,
            "eligible_promotion_decision": expected_decision,
            "promotion_decision_pass": promotion_decision_pass,
            "all_controlling_gates_pass": all_controlling_gates_pass,
        },
        "material_model_risk_clearance": {
            "cleared": model_risk_cleared,
            "reason": clearance["reason"],
        },
        "eligible_for_cio_framework": eligible,
        "decision": "ELIGIBLE_TO_ENTER_CIO_FRAMEWORK" if eligible else "NOT_CIO_ELIGIBLE",
        "guardrail": (
            "This readiness score is not a probability. A high weighted score cannot "
            "override a failed critical dimension, controlling promotion gate, or "
            "uncleared material model-risk defect."
        ),
        "dimensions": dimension_rows,
    }


def evaluate_files(policy_path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    policy = load_json(policy_path)
    validate_policy(policy)
    robust_path = ROOT / policy["controlling_evidence"]["robust_evaluation_summary"]
    robust = load_json(robust_path)
    return compute_status(policy, robust)


def canonical_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, indent=2, allow_nan=False) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="write the deterministic status file")
    mode.add_argument("--check", action="store_true", help="fail if committed status differs from recomputation")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    status = evaluate_files(args.policy)
    text = canonical_json(status)
    target = args.out if args.out.is_absolute() else ROOT / args.out

    if args.write:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    elif args.check:
        try:
            committed = target.read_text(encoding="utf-8")
        except OSError as exc:
            raise ReadinessError(f"committed readiness status missing: {target}") from exc
        if committed != text:
            print(
                "institutional readiness status is stale or inconsistent; run "
                "`python scripts/institutional_readiness.py --write` and review the evidence change",
                file=sys.stderr,
            )
            raise SystemExit(1)
    else:
        print(text, end="")

    print(
        json.dumps(
            {
                "score": status["score"]["rounded_1dp"],
                "decision": status["decision"],
                "eligible_for_cio_framework": status["eligible_for_cio_framework"],
            }
        ),
        file=sys.stderr if not args.write else sys.stdout,
    )


if __name__ == "__main__":
    main()
