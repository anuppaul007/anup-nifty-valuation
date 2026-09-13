"""Append-only as-observed evidence. Never backdate first-seen timestamps."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, subprocess

ROOT = Path(__file__).resolve().parents[1]

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def immutable(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        old = json.loads(path.read_text())
        # Preserve the original capture time when identical evidence is seen again.
        a, b = dict(old), dict(value)
        a.pop('first_seen_at', None); b.pop('first_seen_at', None)
        if a != b:
            raise ValueError(f'Refusing to rewrite frozen evidence: {path}')
        return old
    with path.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(value, indent=2, allow_nan=False) + '\n')
    return value

def archive(root=ROOT, now=None):
    now = now or datetime.now(timezone.utc).isoformat(timespec='seconds')
    packet = json.loads((root/'data/latest.json').read_text())
    policy = json.loads((root/'validation_policy.json').read_text())
    model = (root/'model.js').read_text()
    # Include upstream scoring and timing rules, not just the allocation constants.
    files = [root/'model.js', root/'validation_policy.json', root/'requirements.txt']
    # Freeze all policy and valuation definitions, not just one policy file.
    for name in ['valuation.js','robustness.js','robust_evaluation_policy.json','trend_policy_v1.json','release_timing_policy.json','research_trial_registry.json']:
        if (root/name).exists():files.append(root/name)
    calibration=root/'data/pb_calibration_v3_10.json'
    if calibration.exists():files.append(calibration)
    files += sorted((root/'scripts').glob('*.py'))
    hashes = {str(p.relative_to(root)): digest(p.read_text()) for p in files}
    version = digest(canonical(hashes))
    result = subprocess.run(['node', '-e', "const fs=require('fs'),M=require('./model.js'),x=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify({parameters:M.C,result:M.calculate(x.packet,new Date(x.now))}));"], cwd=root, input=canonical({'packet':packet,'now':now}), text=True, capture_output=True, check=True)
    checked = json.loads(result.stdout)
    folder = root/'data/evidence'
    config = immutable(folder/'models'/f'{version}.json', {'schema_version':1,'first_seen_at':now,'version':version,'file_hashes':hashes,'parameters':checked['parameters'],'model_source':model,'pipeline_sources':{str(p.relative_to(root)):p.read_text() for p in files},'evaluation_policy':policy,'historical_parameter_freeze_claim':False})
    packet_id = digest(canonical({'packet':packet,'model_version':version}))
    snap_path = folder/'snapshots'/f'{packet_id}.json'
    # Reobserving the same packet must not revise the original result as it ages.
    if snap_path.exists():
        snap = json.loads(snap_path.read_text())
        if snap['packet'] != packet or snap['model_version'] != version:
            raise ValueError('Snapshot content mismatch')
    else:
        snap = immutable(snap_path, {'schema_version':1,'first_seen_at':now,'id':packet_id,'model_version':version,'packet':packet,'calculation':checked['result'],'availability_basis':'First observed by this project. This is not the original source publication timestamp.'})
    month = snap['first_seen_at'][:7]
    decision_path = folder/'decisions'/f'{month}.json'
    if snap['calculation'].get('allocationReady') and not decision_path.exists():
        immutable(decision_path, {'month':month,'first_seen_at':snap['first_seen_at'],'snapshot_id':packet_id,'model_version':version,'equity_pct':snap['calculation']['final'],'decision_rule':'First eligible archived publication observed this month; not necessarily the first calendar day. No retroactive entry.'})
    snapshots = [json.loads(p.read_text()) for p in sorted((folder/'snapshots').glob('*.json'))]
    decisions = [json.loads(p.read_text()) for p in sorted((folder/'decisions').glob('*.json'))] if (folder/'decisions').exists() else []
    manifest = {'schema_version':1,'updated_at':now,'archive_started_at':min(s['first_seen_at'] for s in snapshots),'snapshot_count':len(snapshots),'decision_count':len(decisions),'current_model':version,'model_first_seen_at':config['first_seen_at'],'latest_snapshot_id':packet_id,'original_release_vintages_verified':False,'historical_full_model_backtest_validated':False,'policy':policy,'decisions':decisions}
    (root/'data/evidence_status.json').write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')
    return manifest

if __name__ == '__main__':
    r=archive();print(json.dumps({k:r[k] for k in ['snapshot_count','decision_count','current_model']}))
