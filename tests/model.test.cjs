const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const M=require('../model.js');
const now=new Date('2026-09-11T12:00:00Z');
function fixture(){
 const d=JSON.parse(fs.readFileSync(require.resolve('./fixtures/live_packet.json'),'utf8'));
 d.generated_at='2026-09-11T11:46:28Z';d.model_version='3.12-evidence-first-1';d.nifty={date:'2026-09-10',level:23477.8,pe:19.85,pb:2.84,div_yield:1.21,gsec10:6.88,gsec_meta:{asof:'2026-09-10',status:'live',max_age_days:7}};
 d.earnings={score:-.3201937701240839,asof:'2026-08-31',coverage:1};
 d.trend={status:'live',policy_id:'trend-sma10-minus20-v1',asof:'2026-08-31',completed_month:'2026-08',completed_month_close:24000,sma10:23500,lookback_months:10,risk_off:false,risk_off_adjustment_pp:0};
 const score=-.3061910122582852;d.macro.score=score;d.macro.active_block_weight=1;
 for(const f of Object.values(d.macro.factors)){f.score=score;f.status='live';f.asof='2026-09-10';}
 d.macro.china_pmi.score=score;d.macro.domestic.score=score;
 for(const f of Object.values(d.macro.domestic.factors)){f.score=score;f.status='live';f.asof='2026-09-10';}
 return d;
}
test('known snapshot arithmetic uses earnings and trend live while macro is shadow only',()=>{
 const r=M.calculate(fixture(),now);
 assert(Math.abs(r.core-81.14682556581988)<1e-10);assert.equal(r.coverage,1);
 assert.equal(r.macroEligible,true);assert.equal(r.macroContextEligible,true);assert.equal(r.trendEligible,true);assert.equal(r.allocationReady,true);
 assert.equal(r.damp,1);assert.equal(r.ma,0);assert(Math.abs(r.macroShadowAdjustment-(-.3061910122582852*6))<1e-12);
 assert.equal(r.ta,0);assert(Math.abs(r.L.reduce((s,x)=>s+x.weight,0)-100)<1e-12);
 assert(Math.abs(r.final-(r.core+r.ea+r.ta))<1e-12);
});
test('partial macro coverage withholds only shadow context, not the live allocation',()=>{
 const d=fixture();d.macro.active_block_weight=.99;let r=M.calculate(d,now);
 assert(r.coverage<1);assert.equal(r.macroEligible,false);assert.equal(r.ma,0);assert.equal(r.macroShadowAdjustment,null);assert.equal(r.allocationReady,true);
 d.macro.active_block_weight=.53;r=M.calculate(d,now);assert.equal(r.allocationReady,true);assert.equal(r.holdReason,null);
});
test('0 and 100 valuation-core equity remain attainable and curve is monotone',()=>{
 assert.equal(M.curve(-2.5),100);assert.equal(M.curve(2.5),0);
 let previous=100;for(let z=-4;z<=4;z+=.02){const x=M.curve(z);assert(x<=previous+1e-10);previous=x;}
});
test('unknown or inconsistent macro cannot change or block a live allocation',()=>{
 const base=M.calculate(fixture(),now);assert(base.allocationReady);
 for(const change of [d=>d.macro.score=null,d=>d.macro_stale=true,d=>d.macro.active_block_weight=.5]){
  const d=fixture();change(d);const r=M.calculate(d,now);assert.equal(r.ma,0);assert.equal(r.macroEligible,false);assert.equal(r.macroShadowAdjustment,null);assert.equal(r.allocationReady,true);assert.equal(r.final,base.final);
 }
});
test('stale packet still withholds allocation through required earnings and trend gates',()=>{
 const d=fixture();d.generated_at='2026-09-01';const r=M.calculate(d,now);assert.equal(r.allocationReady,false);
});
test('incomplete earnings history still withholds allocation',()=>{
 const d=fixture();d.earnings.coverage=.7;const r=M.calculate(d,now);assert.equal(r.earningsComplete,false);assert.equal(r.allocationReady,false);assert.equal(r.final,null);
});
test('undated bond yield is excluded rather than relabelled as current',()=>{
 const d=fixture();delete d.nifty.gsec_meta;const r=M.calculate(d,now);
 assert.equal(r.gsecEligible,false);assert.equal(r.L[2].weight,0);assert(r.fundamentalCoverage<1);assert.equal(r.allocationReady,false);assert.equal(r.final,null);
});
test('invalid, stale and future NIFTY withhold allocation',()=>{
 for(const v of [null,0,NaN,'19.85']){const d=fixture();d.nifty.pe=v;assert.equal(M.calculate(d,now).valid,false);}
 for(const v of ['2026-08-01','2026-09-12',null]){const d=fixture();d.nifty.date=v;assert.equal(M.calculate(d,now).valid,false);}
});
test('failed browser reload clears a previously displayed allocation',()=>{
 const nodes=new Map();const node=id=>nodes.get(id)||nodes.set(id,{textContent:'81%',style:{},className:'',innerHTML:''}).get(id);
 const context={AnupHealth:require('../health.js'),setInterval:()=>0,AnupModel:M,document:{querySelector:node,querySelectorAll:()=>[]},AbortController,Date,console,setTimeout:()=>0,clearTimeout:()=>{},fetch:()=>new Promise(()=>{})};
 vm.createContext(context);vm.runInContext(fs.readFileSync(require.resolve('../app.js'),'utf8'),context);
 vm.runInContext("clearAllocation('unavailable')",context);
 assert.equal(node('#eq').textContent,'—');assert.equal(node('#debt').textContent,'—');assert.equal(node('#eqbar').style.width,'0%');
});
test('fresh wrapper cannot make bad macro context authoritative',()=>{
 const base=M.calculate(fixture(),now);assert(base.allocationReady);
 for(const mutate of [d=>d.macro.factors.vix.asof='2026-01-01',d=>delete d.macro.factors.vix,d=>d.macro.factors.vix.score=NaN,d=>d.macro.china_pmi.new_orders=null,d=>d.macro.domestic.factors.india_cpi_yoy.asof='2026-01-01',d=>d.macro.score=.9]){
  const d=fixture();mutate(d);const r=M.calculate(d,now);assert.equal(r.macroEligible,false);assert.equal(r.macroShadowAdjustment,null);assert.equal(r.allocationReady,true);assert.equal(r.final,base.final);
 }
});
test('cheap-side earnings authority remains live while macro stays shadow',()=>{
 const d=fixture();d.nifty.pe=8;d.nifty.pb=1.1;d.nifty.div_yield=3;
 d.macro.score=-1;for(const f of Object.values(d.macro.factors))f.score=-1;d.macro.china_pmi.score=-1;d.macro.domestic.score=-1;for(const f of Object.values(d.macro.domestic.factors))f.score=-1;
 d.earnings.score=-1;const r=M.calculate(d,now);
 assert(r.z<0);assert.equal(r.damp,1);assert.equal(r.ma,0);assert.equal(r.macroShadowAdjustment,-6);assert.equal(r.ea,-6);assert(Math.abs(r.final-M.clip(r.core-6+r.ta,0,100))<1e-12);
});
test('macro score cannot move live allocation but shadow adjustment is monotone',()=>{
 for(let pe=8;pe<=45;pe+=1){let previousShadow=-Infinity;let live=null;
  for(const score of [-1,-.5,0,.5,1]){const d=fixture();d.nifty.pe=pe;d.macro.score=score;for(const f of Object.values(d.macro.factors))f.score=score;d.macro.china_pmi.score=score;d.macro.domestic.score=score;for(const f of Object.values(d.macro.domestic.factors))f.score=score;
   const r=M.calculate(d,now);assert(r.allocationReady);assert.equal(r.ma,0);assert(r.final>=0&&r.final<=100);if(live===null)live=r.final;else assert(Math.abs(r.final-live)<1e-12);assert(r.macroShadowAdjustment>=previousShadow-1e-9);previousShadow=r.macroShadowAdjustment;
   if(r.z<0)assert.equal(r.damp,1);else assert(r.damp<=1&&r.damp>=0);
  }
 }
});
test('trend crash guard is one-way, subtracts exactly 20 pp and never increases equity',()=>{
 const on=fixture(),ron=M.calculate(on,now);const off=fixture();off.trend.completed_month_close=22000;off.trend.sma10=23500;off.trend.risk_off=true;off.trend.risk_off_adjustment_pp=-20;
 const roff=M.calculate(off,now);assert.equal(roff.trendRiskOff,true);assert.equal(roff.ta,-20);assert(Math.abs(roff.final-M.clip(ron.final-20,0,100))<1e-12);assert(roff.final<=ron.final);
});
test('missing, stale or inconsistent trend input fails closed',()=>{
 for(const mutate of [d=>delete d.trend,d=>d.trend.asof='2026-06-01',d=>d.trend.sma10=null,d=>d.trend.risk_off=true,d=>d.trend.policy_id='other']){
  const d=fixture();mutate(d);const r=M.calculate(d,now);assert.equal(r.trendEligible,false);assert.equal(r.allocationReady,false);assert.equal(r.final,null);
 }
});
test('display-only nominal yield cannot dilute macro context and a broken context cannot block live',()=>{
 const d=fixture(),before=M.calculate(d,now);d.macro.factors.us_10y={display_only:true,value:4.95,z:null,score:null,status:'live',asof:'2026-09-10'};
 assert.equal(M.calculate(d,now).final,before.final);
 d.macro.factors.vix.display_only=true;const broken=M.calculate(d,now);assert.equal(broken.macroEligible,false);assert.equal(broken.allocationReady,true);assert.equal(broken.final,before.final);
});