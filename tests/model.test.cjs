const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const M=require('../model.js');
const now=new Date('2026-09-11T12:00:00Z');
function fixture(){return{schema_version:4,generated_at:'2026-09-11T11:46:28Z',nifty:{date:'2026-09-10',level:23477.8,pe:19.85,pb:2.84,div_yield:1.21,gsec10:6.88,gsec_meta:{asof:'2026-09-10',status:'live',max_age_days:7}},earnings:{score:-.3201937701240839,asof:'2026-08-31',coverage:1},macro:{score:-.3061910122582852,active_block_weight:1}};}
test('known snapshot arithmetic works when complete-data gate passes',()=>{
 const r=M.calculate(fixture(),now);
 assert(Math.abs(r.core-83.1)<.06);
 assert.equal(r.macroEligible,true);assert.equal(r.allocationReady,true);
 assert(Math.abs(r.ma-(-.3061910122582852*6*r.damp))<1e-12);
 assert(Math.abs(r.L.reduce((s,x)=>s+x.weight,0)-100)<1e-12);
 assert(Math.abs(r.final-(r.core+r.ea+r.ma))<1e-12);
});
test('partial macro coverage withholds allocation instead of neutral filling',()=>{
 const d=fixture();d.macro.active_block_weight=.99;let r=M.calculate(d,now);
 assert.equal(r.macroEligible,false);assert.equal(r.ma,0);assert.equal(r.allocationReady,false);assert.equal(r.final,null);
 d.macro.active_block_weight=.53;r=M.calculate(d,now);assert.equal(r.allocationReady,false);assert.match(r.holdReason,/coverage/);
});
test('0 and 100 valuation-core equity remain attainable and curve is monotone',()=>{
 assert.equal(M.curve(-2.5),100);assert.equal(M.curve(2.5),0);
 let previous=100;for(let z=-4;z<=4;z+=.02){const x=M.curve(z);assert(x<=previous+1e-10);previous=x;}
});
test('unknown or stale macro cannot publish an allocation',()=>{
 for(const change of [d=>d.macro.score=null,d=>d.macro_stale=true,d=>d.generated_at='2026-09-01',d=>d.schema_version=3]){
  const d=fixture();change(d);const r=M.calculate(d,now);assert.equal(r.ma,0);assert.equal(r.allocationReady,false);assert.equal(r.final,null);
 }
});
test('incomplete earnings history also withholds allocation',()=>{
 const d=fixture();d.earnings.coverage=.7;const r=M.calculate(d,now);assert.equal(r.earningsComplete,false);assert.equal(r.allocationReady,false);assert.equal(r.final,null);
});
test('undated bond yield is excluded rather than relabelled as current',()=>{
 const d=fixture();delete d.nifty.gsec_meta;const r=M.calculate(d,now);
 assert.equal(r.gsecEligible,false);assert.equal(r.L[2].weight,0);assert(r.fundamentalCoverage<1);
 assert.equal(r.allocationReady,false);assert.equal(r.final,null);
});
test('invalid, stale and future NIFTY withhold allocation',()=>{
 for(const v of [null,0,NaN,'19.85']){const d=fixture();d.nifty.pe=v;assert.equal(M.calculate(d,now).valid,false);}
 for(const v of ['2026-08-01','2026-09-12',null]){const d=fixture();d.nifty.date=v;assert.equal(M.calculate(d,now).valid,false);}
});
test('failed browser reload clears a previously displayed allocation',()=>{
 const nodes=new Map();const node=id=>nodes.get(id)||nodes.set(id,{textContent:'81%',style:{},className:'',innerHTML:''}).get(id);
 const context={AnupModel:M,document:{querySelector:node},AbortController,Date,console,setTimeout:()=>0,clearTimeout:()=>{},fetch:()=>new Promise(()=>{})};
 vm.createContext(context);vm.runInContext(fs.readFileSync(require.resolve('../app.js'),'utf8'),context);
 vm.runInContext("clearAllocation('unavailable')",context);
 assert.equal(node('#eq').textContent,'—');assert.equal(node('#debt').textContent,'—');assert.equal(node('#eqbar').style.width,'0%');
});
