"""Research-only calibration anchor and publication guards (no live authority)."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path


def validate_anchor(document):
    if not isinstance(document, dict):
        return None, 'invalid_reliability_document'
    comparison = document.get('current_formula_comparison')
    if not isinstance(comparison, dict):
        return None, 'missing_comparison'
    if 'new_policy_equity_pct' not in comparison:
        return None, 'missing_anchor'
    value = comparison['new_policy_equity_pct']
    if value is None:
        return None, 'null_anchor'
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None, 'invalid_anchor_type'
    try:
        expected = float(value)
    except (ValueError, TypeError, OverflowError):
        return None, 'invalid_anchor_type'
    if not math.isfinite(expected):
        return None, 'nonfinite_anchor'
    if not 0 <= expected <= 100:
        return None, 'out_of_range_anchor'
    return expected, None


def write_report(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def write_withheld(path, reason, version):
    """Do not output partial calibration results or imply reproduction success."""
    report = {
        'schema_version': 2,
        'generated_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'research_only': True, 'model_version': version,
        'publication_status': 'withheld', 'withheld_reason': reason,
        'anchor_status': 'unverified', 'production_reproduction': None,
        'variants': [], 'return_data_used': False,
        'live_model_changed': False, 'live_allocation_changed': False
    }
    write_report(path, report)
    print(json.dumps({'publication_status': 'withheld', 'reason': reason}))


def verify_publication(path):
    """CI must fail if the report was withheld, missing, stale or malformed."""
    target = Path(path)
    if not target.is_file():
        raise SystemExit('calibration_publication_blocked: artifact missing')
    try:
        report = json.loads(target.read_text(encoding='utf-8'))
    except (ValueError, OSError) as exc:
        raise SystemExit('calibration_publication_blocked: artifact unreadable') from exc
    if not isinstance(report, dict):
        raise SystemExit('calibration_publication_blocked: invalid artifact')
    if report.get('publication_status') != 'published':
        raise SystemExit('calibration_publication_blocked: ' + str(report.get('withheld_reason') or 'not_published'))
    if (report.get('schema_version') != 2
            or report.get('research_only') is not True
            or report.get('live_model_changed') is not False
            or report.get('live_allocation_changed') is not False
            or report.get('return_data_used') is not False
            or report.get('anchor_status') != 'verified'
            or not isinstance(report.get('production_reproduction'), dict)
            or not isinstance(report.get('variants'), list)
            or len(report['variants']) != 9):
        raise SystemExit('calibration_publication_blocked: incomplete or unsafe artifact')
    print('calibration_publication_verified: research-only artifact')
    return report


def enforce_reproduction(path, version, actual, expected):
    """A numerical mismatch is a hard error, never a withheld green publication."""
    if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isfinite(float(actual)):
        write_withheld(path, 'invalid_production_equity', version)
        raise RuntimeError('invalid_production_equity')
    if not 0 <= actual <= 100:
        write_withheld(path, 'invalid_production_equity', version)
        raise RuntimeError('invalid_production_equity')
    if abs(actual - expected) > 1e-8:
        write_withheld(path, 'production_reproduction_mismatch', version)
        raise RuntimeError(f'production_reproduction_mismatch_{actual}_{expected}')


# Frozen source set from scripts/reliability_audit.py. Never accept a caller-provided
# list of hashes: doing so would let a stale receipt omit its changed source.
RELIABILITY_SOURCE_PATHS = (
    'model.js', 'valuation.js', 'requirements.txt', 'data/latest.json',
    'data/pb_calibration_v3_10.json', 'robust_evaluation_policy.json',
    'validation_policy.json', 'trend_policy_v1.json',
    'release_timing_policy.json', 'research_trial_registry.json',
)


def validate_provenance(document, *, root, latest, model_version):
    """Bind a numerical anchor to the exact point-in-time inputs that produced it.

    A matching allocation percentage alone is insufficient: capped/rounded
    allocations can remain equal even after inputs or policy files change.
    No wall-clock freshness threshold is invented for retrospective research;
    exact packet identity and a timezone-aware evaluation vintage are required.
    """
    import hashlib
    import re

    if not isinstance(document, dict):
        return 'invalid_reliability_document'
    if not isinstance(latest, dict):
        return 'invalid_latest_packet'
    if document.get('schema_version') != 1:
        return 'invalid_reliability_schema'
    if document.get('status') != 'structural_checks_passed':
        return 'unverified_reliability_status'
    if document.get('allocation_ready_at_capture') is not True:
        return 'allocation_not_ready_at_capture'
    if document.get('hold_reason') is not None:
        return 'reliability_hold_reason'
    if document.get('model_version') != model_version or latest.get('model_version') != model_version:
        return 'model_version_mismatch'
    evaluated = document.get('evaluated_at')
    generated = latest.get('generated_at')
    if not isinstance(evaluated, str) or not isinstance(generated, str) or evaluated != generated:
        return 'stale_reliability_vintage'
    try:
        evaluation_time = datetime.fromisoformat(evaluated.replace('Z', '+00:00'))
        if evaluation_time.tzinfo is None or evaluation_time.utcoffset() is None:
            return 'invalid_evaluation_timestamp'
    except ValueError:
        return 'invalid_evaluation_timestamp'
    hashes = document.get('source_hashes')
    if not isinstance(hashes, dict) or set(hashes) != set(RELIABILITY_SOURCE_PATHS):
        return 'missing_or_extra_source_hash'
    root = Path(root)
    for relative in RELIABILITY_SOURCE_PATHS:
        recorded = hashes[relative]
        if not isinstance(recorded, str) or re.fullmatch(r'[0-9a-f]{64}', recorded) is None:
            return 'invalid_source_hash'
        try:
            actual = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        except OSError:
            return 'unavailable_source_file'
        if actual != recorded:
            return 'stale_source_hash'
    return None
