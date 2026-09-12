"""Independent publication watchdog; emits status even when a check fails."""
import base64, hashlib, json, os, subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
REPO='anuppaul007/anup-nifty-valuation'

def packet_check(packet,now):
    if packet.get('schema_version')!=4:return False,'Unsupported schema; upgrade required'
    try:
        stamp=datetime.fromisoformat(packet['generated_at'].replace('Z','+00:00'))
        age=(now-stamp).total_seconds()/3600
    except (ValueError,KeyError,TypeError):return False,'Invalid packet publication timestamp'
    return 0<=age<=72,f'Packet age {age:.2f} hours; maximum 72 hours'

def get(url):
    headers={'User-Agent':'Anup-Nifty-Publication-Monitor','Accept':'application/vnd.github+json','Cache-Control':'no-cache'}
    token=os.environ.get('GH_TOKEN')
    if token and url.startswith('https://api.github.com/'):
        headers['Authorization']='Bearer '+token
    with urlopen(Request(url,headers=headers),timeout=25) as response:return response.read()

def main():
    now=datetime.now(timezone.utc);checks=[]
    def run(name,fn):
        try:ok,detail=fn()
        except Exception as e:ok,detail=False,type(e).__name__+': '+str(e)
        checks.append({'name':name,'ok':ok,'detail':detail})
    try:
        raw=(ROOT/'data/latest.json').read_bytes();packet=json.loads(raw)
        if not isinstance(packet,dict):raise ValueError('Packet must be an object')
    except (OSError,ValueError) as e:
        raw=b'';packet={};checks.append({'name':'packet_parse','ok':False,'detail':str(e)})
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    run('packet_freshness',lambda:packet_check(packet,now))
    def integrity():
        api=json.loads(get(f'https://api.github.com/repos/{REPO}/contents/data/latest.json?ref={sha}'))
        decoded=base64.b64decode(api['content'])
        other=get(f'https://raw.githubusercontent.com/{REPO}/{sha}/data/latest.json')
        ok=raw==decoded==other
        return ok,('Pinned commit API, raw source and checkout bytes match: ' if ok else 'Published source bytes differ at pinned commit: ')+hashlib.sha256(raw).hexdigest()
    run('published_bytes',integrity)
    def refresh_status():
        data=json.loads(get(f'https://api.github.com/repos/{REPO}/actions/workflows/refresh-data.yml/runs?branch=main&status=completed&per_page=10'))
        runs=[r for r in data['workflow_runs'] if r.get('conclusion')!='cancelled']
        if not runs:return False,'No completed refresh found'
        last=runs[0];return last['conclusion']=='success',f"Latest completed refresh: {last['conclusion']} · {last['html_url']}"
    run('refresh_workflow',refresh_status)
    def allocation_gate():
        result=subprocess.run(['node','-e',"const fs=require('fs'),M=require('./model.js');process.stdout.write(JSON.stringify(M.calculate(JSON.parse(fs.readFileSync(0,'utf8')))));"],cwd=ROOT,input=raw.decode(),capture_output=True,text=True,check=True)
        r=json.loads(result.stdout);return bool(r.get('allocationReady')),r.get('holdReason') or r.get('reason') or 'Defined input gates passed'
    run('allocation_inputs',allocation_gate)
    out={'schema_version':1,'checked_at':now.isoformat(timespec='seconds'),'source_commit':sha,'packet_generated_at':packet.get('generated_at'),'status':'healthy' if all(c['ok'] for c in checks) else 'attention_required','checks':checks,'scope':'Operational checks only; not investment validation. A delayed watchdog can also miss failures; the website checks this status age.'}
    target=ROOT/'data/health.json';temp=target.with_suffix('.tmp');temp.write_text(json.dumps(out,indent=2)+'\n');temp.replace(target)
    print(json.dumps(out));return 0 if out['status']=='healthy' else 1

if __name__=='__main__':raise SystemExit(main())
