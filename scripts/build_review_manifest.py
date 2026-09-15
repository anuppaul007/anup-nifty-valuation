#!/usr/bin/env python3
"""Build a deterministic review manifest for an immutable repository commit.

The manifest is evidence about *what* was reviewed, not evidence that the model
works. It records the exact Git commit, tracked-tree cleanliness, environment
versions, and SHA-256 digests for critical model/governance/evidence files.

By default a dirty tracked tree is refused. Untracked files are ignored so the
manifest itself can be written into the working directory without invalidating
the target. Use --allow-dirty only when intentionally documenting a non-clean
working tree; such a manifest should not be described as an immutable release.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
from importlib import metadata

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    'model.js',
    'requirements.txt',
    'validation_policy.json',
    'robust_evaluation_policy.json',
    'implementation_realism_policy.json',
    'current_definition_aggregation_policy.json',
    'review_scope_v1.json',
    'INDEPENDENT_REVIEW.md',
    'EXTERNAL_REVIEW_PACKET.md',
    'INSTITUTIONAL_READINESS.md',
    'institutional_readiness_policy_v1.json',
    'CURRENT_DEFINITION_ALGEBRA_CORRECTION.md',
    'research_trial_registry.json',
    'scripts/robust_evaluation.py',
    'scripts/calibration_stability_audit.py',
    'scripts/implementation_realism_audit.py',
    'scripts/current_definition_aggregation.py',
    'scripts/institutional_readiness.py',
    'data/latest.json',
    'data/robust_evaluation_summary.json',
    'data/calibration_stability_audit.json',
    'data/institutional_readiness.json',
]

OPTIONAL_FILES = [
    'data/implementation_realism_audit.json',
    'data/benchmark_audit.json',
    'data/sma10_insurance_audit.json',
    'data/sma10_episode_audit.json',
    'data/macro_authority_audit.json',
    'data/reliability_audit.json',
]


def run_git(*args: str) -> str:
    p = subprocess.run(
        ['git', *args], cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return p.stdout.strip()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def file_record(relative: str, required: bool) -> dict:
    path = ROOT / relative
    if not path.exists():
        if required:
            raise FileNotFoundError(f'required review file missing: {relative}')
        return {'path': relative, 'required': False, 'present': False}
    if not path.is_file():
        raise RuntimeError(f'review path is not a regular file: {relative}')
    return {
        'path': relative,
        'required': bool(required),
        'present': True,
        'size_bytes': int(path.stat().st_size),
        'sha256': sha256_file(path),
    }


def parse_requirement_names(path: Path) -> list[str]:
    names: list[str] = []
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        # Enough for this repository's exact-version requirements file while
        # refusing to invent versions for URLs/options/markers.
        token = re.split(r'[<>=!~;\s\[]', line, maxsplit=1)[0].strip()
        if token and not token.startswith('-'):
            names.append(token)
    return names


def installed_requirement_versions() -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for name in parse_requirement_names(ROOT / 'requirements.txt'):
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = None
    return out


def command_version(command: list[str]) -> str | None:
    try:
        p = subprocess.run(command, cwd=ROOT, check=True, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        text = (p.stdout or p.stderr).strip()
        return text or None
    except (OSError, subprocess.CalledProcessError):
        return None


def build_manifest(allow_dirty: bool = False) -> dict:
    commit = run_git('rev-parse', 'HEAD')
    tracked_status = run_git('status', '--porcelain', '--untracked-files=no')
    clean = tracked_status == ''
    if not clean and not allow_dirty:
        raise RuntimeError(
            'tracked working tree is dirty; commit or restore changes before '
            'building an immutable review manifest (or use --allow-dirty to '
            'document the dirty state explicitly)'
        )

    files = [file_record(p, True) for p in REQUIRED_FILES]
    files.extend(file_record(p, False) for p in OPTIONAL_FILES)
    return {
        'schema_version': 1,
        'generated_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'purpose': 'External-review identity manifest; not evidence of investment efficacy or independent validation.',
        'repository': 'anuppaul007/anup-nifty-valuation',
        'commit_sha': commit,
        'tracked_tree_clean': clean,
        'tracked_status_porcelain': tracked_status.splitlines(),
        'allow_dirty_used': bool(allow_dirty),
        'environment': {
            'python': sys.version.replace('\n', ' '),
            'python_implementation': platform.python_implementation(),
            'platform': platform.platform(),
            'node': command_version(['node', '--version']),
            'git': command_version(['git', '--version']),
            'requirements_installed': installed_requirement_versions(),
        },
        'files': files,
        'review_guardrail': (
            'Matching hashes establish the reviewed artifact identity only. '
            'They do not establish point-in-time data validity, statistical '
            'efficacy, implementation quality, or reviewer independence.'
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='review_manifest.json',
                    help='output JSON path (default: review_manifest.json)')
    ap.add_argument('--allow-dirty', action='store_true',
                    help='record rather than reject a dirty tracked tree')
    args = ap.parse_args()
    out = build_manifest(allow_dirty=args.allow_dirty)
    target = Path(args.out)
    if not target.is_absolute():
        target = ROOT / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({
        'commit_sha': out['commit_sha'],
        'tracked_tree_clean': out['tracked_tree_clean'],
        'required_files': sum(1 for x in out['files'] if x['required']),
        'optional_present': sum(1 for x in out['files'] if not x['required'] and x['present']),
        'output': str(target),
    }, indent=2))


if __name__ == '__main__':
    main()
