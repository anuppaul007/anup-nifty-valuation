const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('fs');
const path=require('path');
const C=require('../covariance_challenger.js');
const policy=require('../covariance_challenger_policy.json');

const fixture=()=>JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/live_packet.json'),'utf8'));
const nowFor=d=>new Date(d.generated_at);

test('frozen challenger weights match preregistered policy and sum to one',()=>{
  const p=policy.construction.frozen_weights;
  const expected=C.LABELS.map(k=>p[k]);
  assert.deepEqual([...C.WEIGHTS],expected);
  assert(Math.abs(C.WEIGHTS.reduce((a,b)=>a+b,0)-1)<1e-9);
  assert(C.WEIGHTS.every(x=>x>0));
  assert.equal(policy.construction.shrinkage_lambda,0.5);
  assert.equal(policy.source_geometry.return_data_used_to_choose_construction,false);
});

test('challenger inherits production eligibility gates and has zero live authority',()=>{
  const d=fixture();
  const r=C.compute(d,nowFor(d));
  assert.equal(r.valid,true);
  assert.equal(r.allocationReady,true);
  assert.equal(r.live_authority,false);
  assert.equal(typeof r.final,'number');
  assert.equal(typeof r.live_final,'number');
  assert(Math.abs(r.difference_vs_live_pp-(r.final-r.live_final))<1e-12);
});

test('stale required bond evidence withholds the shadow allocation',()=>{
  const d=fixture();
  d.nifty.gsec_meta.asof='2020-01-01';
  const r=C.compute(d,nowFor(d));
  assert.equal(r.allocationReady,false);
  assert.equal(r.final,null);
  assert.equal(r.live_authority,false);
});

test('version mismatch is rejected rather than silently evaluated',()=>{
  const d=fixture();d.model_version='wrong-version';
  const r=C.compute(d,nowFor(d));
  assert.equal(r.valid,false);
  assert.equal(r.allocationReady,false);
});
