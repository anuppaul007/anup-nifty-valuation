"""Offline, reproducible structural checks. This is not independent validation."""
from pathlib import Path
import hashlib,json,math,subprocess
from datetime import datetime,timezone
import numpy as np

ROOT=Path(__file__).resolve().parents[1]

def build(root=ROOT):
    packet=json.loads((root/'data/latest.json').read_text())
    calibration=json.loads((root/'data/pb_calibration_v3_10.json').read_text())
    vals=[math.log(r[2]/3.54)-.6*math.log((100*r[2]/r[1])/16.15402934929392) for r in calibration['history']]
    offset,scale=float(np.median(vals)),float(np.std(vals))
    code="""const fs=require('fs'),M=require('./model.js'),V=require('./valuation.js'),d=JSON.parse(fs.readFileSync(0,'utf8')),now=new Date(d.generated_at);process.stdout.write(JSON.stringify({version:M.VERSION,constants:M.C,pb_log:M.PB_LOG,result:M.calculate(d,now),valuation:V.assess(d,now)}));"""
    checked=json.loads(subprocess.run(['node','-e',code],cwd=root,input=json.dumps(packet),text=True,capture_output=True,check=True).stdout)
    if abs(offset-checked['pb_log']['offset'])>1e-12 or abs(scale-checked['pb_log']['scale'])>1e-12:raise ValueError('P/B log calibration does not reproduce')
    c=checked['constants']
    old=lambda pe,pb:(pb-c['pbM'])/c['pbS']-c['beta']*(100*pb/pe-c['roeM'])/c['roeS']
    new=lambda pe,pb:(math.log(pb/c['pbM'])-c['beta']*math.log((100*pb/pe)/c['roeM'])-offset)/scale
    checks=0
    for pe in np.arange(5,60.01,.5):
        for pb in np.arange(.5,10.01,.1):
            assert new(pe,pb+.001)>new(pe,pb) and new(pe+.001,pb)>new(pe,pb)
            checks+=1
    r=checked['result'];comparison=None
    if r.get('allocationReady'):
        n=packet['nifty'];old_pb=old(n['pe'],n['pb'])
        old_z=r['z']+(old_pb-r['L'][1]['z'])*c['wPB']/(c['wPE']+c['wPB']+c['wGAP']+c['wDY'])
        f=lambda z:100/(1+math.exp(c['k']*z))
        old_core=max(0,min(100,(f(old_z)-f(c['zc']))/(f(-c['zc'])-f(c['zc']))*100))
        damp=1 if old_z<0 else max(0,1-abs(old_z)/c['zc'])
        old_final=max(0,min(100,old_core+packet['earnings']['score']*c['earnMax']*damp+r['ta']))
        comparison={'scope':'Same current inputs; formula effect only, not a historical return test','old_pb_z':old_pb,'new_pb_z':r['L'][1]['z'],'old_core_equity_pct':old_core,'new_core_equity_pct':r['core'],'old_policy_equity_pct':old_final,'new_policy_equity_pct':r['final'],'change_pp':r['final']-old_final}
    paths=['model.js','valuation.js','requirements.txt','data/latest.json','data/pb_calibration_v3_10.json','robust_evaluation_policy.json','validation_policy.json','trend_policy_v1.json','release_timing_policy.json','research_trial_registry.json']
    hashes={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths}
    return {'schema_version':1,'model_version':checked['version'],'evaluated_at':packet['generated_at'],'evaluation_clock':'Packet generation time; current live eligibility is rechecked in the browser and watchdog','source_hashes':hashes,'status':'structural_checks_passed','allocation_ready_at_capture':bool(r.get('allocationReady')),'hold_reason':r.get('holdReason') or r.get('reason'),'pb_calibration':{'months':len(vals),'offset':offset,'scale':scale,'return_optimization':False},'monotonicity_grid_cases':checks,'old_defect':{'sign_reversal_below_pe':100*c['beta']*c['pbS']/c['roeS'],'example_pe':12,'pb_from':3,'pb_to':3.1,'old_z_change':old(12,3.1)-old(12,3),'new_z_change':new(12,3.1)-new(12,3)},'current_formula_comparison':comparison,'valuation_sensitivity':checked['valuation'],'independent_validation':'not_completed','investment_performance_validation':'not_demonstrated','limitations':['Same developer authored model and checks; Python reproduction is not organizational independence.','The 36-month calibration is short and does not establish intrinsic value.','Reference assumptions, correlated lenses, turnover, taxes and crash gaps remain material.','No synthetic or retrospective observation is counted as a prospective decision.']}

if __name__=='__main__':
    result=build();target=ROOT/'data/reliability_audit.json';tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');tmp.replace(target)
    print(json.dumps({k:result[k] for k in ['status','allocation_ready_at_capture','monotonicity_grid_cases','current_formula_comparison']}))
