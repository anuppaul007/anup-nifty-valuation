"""Research-only calibration anchor and publication guards (no live authority)."""
from datetime import datetime, timezone
import hashlib
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


def screen_receipt(path):
    """Bind research sensitivity inputs to exact bytes; does not certify historical PIT."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError('unavailable_calibration_screen') from exc


def verify_publication(path, *, root=None, latest=None, reliability=None, model_version=None, screen=None):
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
    if root is None or latest is None or reliability is None or model_version is None or screen is None:
        raise SystemExit('calibration_publication_blocked: provenance context missing')
    try:
        current_screen_hash = screen_receipt(screen)
    except ValueError as exc:
        raise SystemExit('calibration_publication_blocked: unavailable_calibration_screen') from exc
    if report.get('calibration_screen_sha256') != current_screen_hash:
        raise SystemExit('calibration_publication_blocked: stale_calibration_screen')
    reason = validate_provenance(reliability, root=root, latest=latest, model_version=model_version)
    if reason:
        raise SystemExit('calibration_publication_blocked: ' + reason)
    expected, reason = validate_anchor(reliability)
    if reason:
        raise SystemExit('calibration_publication_blocked: ' + reason)
    receipt = {'evaluated_at': reliability['evaluated_at'], 'source_hashes': reliability['source_hashes']}
    if report.get('anchor_provenance') != receipt:
        raise SystemExit('calibration_publication_blocked: stale_or_missing_receipt')
    # A matching generated_at is not sufficient: consumers must not receive
    # a receipt whose quoted current-market fields were changed or replayed.
    # Compare the entire research packet against the already provenance-bound
    # latest input; no historical or live allocation policy is modified.
    try:
        n = latest['nifty']
        expected_packet = {
            'generated_at': latest['generated_at'],
            'nifty_date': n['date'], 'level': n['level'],
            'pe': n['pe'], 'pb': n['pb'],
            'dividend_yield': n['div_yield'], 'gsec10': n['gsec10'],
            'gsec_asof': n['gsec_meta']['asof'],
        }
    except (KeyError, TypeError):
        raise SystemExit('calibration_publication_blocked: invalid_latest_packet')
    if report.get('model_version') != model_version or report.get('current_packet') != expected_packet:
        raise SystemExit('calibration_publication_blocked: stale_report_packet')
    # The deterministic payload replay check deliberately ignores the
    # nondeterministic audit clock. Validate that clock separately so a
    # forged pre-source, future, naive or malformed publication vintage
    # cannot pass while all numeric fields and source receipts still match.
    # No retrospective age/freshness threshold is introduced here.
    publication_vintage = report.get('generated_at')
    if not isinstance(publication_vintage, str):
        raise SystemExit('calibration_publication_blocked: invalid_publication_vintage')
    try:
        published_at = datetime.fromisoformat(publication_vintage.replace('Z', '+00:00'))
        source_at = datetime.fromisoformat(latest['generated_at'].replace('Z', '+00:00'))
    except (ValueError, TypeError):
        raise SystemExit('calibration_publication_blocked: invalid_publication_vintage')
    if (published_at.tzinfo is None or published_at.utcoffset() is None
            or source_at.tzinfo is None or source_at.utcoffset() is None):
        raise SystemExit('calibration_publication_blocked: invalid_publication_vintage')
    if published_at < source_at:
        raise SystemExit('calibration_publication_blocked: stale_publication_vintage')
    if published_at > datetime.now(timezone.utc):
        raise SystemExit('calibration_publication_blocked: future_publication_vintage')
    actual = report['production_reproduction'].get('policy_equity_pct')
    if (isinstance(actual, bool) or not isinstance(actual, (int, float))
        or not math.isfinite(float(actual)) or abs(actual - expected) > 1e-8):
        raise SystemExit('calibration_publication_blocked: reproduction_mismatch')
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
