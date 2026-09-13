const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const M=require('../model.js'),V=require('../valuation.js');
const now=new Date('2026-09-12T12:00:00Z');
const fixture=()=>JSON.parse(fs.readFileSync(require.resolve('./fixtures/live_packet.json'),'utf8'));
test('P/B repair removes the low-PE sign reversal across a broad input grid',()=>{
 let count=0;
 for(let pe=5;pe<=60;pe+=.5)for(let pb=.5;pb<=10;pb+=.1){
  assert(M.pbZ(pe,pb+.001)>M.pbZ(pe,pb));
  assert(M.pbZ(pe+.001,pb)>M.pbZ(pe,pb));count++;
 }
 assert(count>10000);
 // Explicit reproduction of the old defect, not merely matching new code.
 const old=(pe,pb)=>(pb-M.C.pbM)/M.C.pbS-M.C.beta*(100*pb/pe-M.C.roeM)/M.C.roeS;
 assert(old(12,3)>old(12,3.1));assert(M.pbZ(12,3)<M.pbZ(12,3.1));
});
test('repricing all ratios together cannot increase equity as the market gets dearer',()=>{
 const d=fixture();let previous=101;
 for(let scale=.2;scale<=3;scale+=.01){
  const x=structuredClone(d);x.nifty.level*=scale;x.nifty.pe*=scale;x.nifty.pb*=scale;x.nifty.div_yield/=scale;
  const r=M.calculate(x,now);assert(r.allocationReady);assert(r.final<=previous+1e-9);previous=r.final;
 }
});
test('packet metadata cannot extend daily yield life or disguise monthly/cache inputs',()=>{
 for(const mutate of [d=>{d.nifty.gsec_meta.asof='2026-06-01';d.nifty.gsec_meta.max_age_days=10000;},d=>d.nifty.gsec_meta.status='lagged',d=>d.nifty.gsec_meta.status='cached',d=>delete d.nifty.gsec_meta.status]){
  const d=fixture();mutate(d);assert.equal(M.calculate(d,now).allocationReady,false);
 }
});
test('invalid score, future earnings month and mixed engine version fail closed',()=>{
 for(const mutate of [d=>d.earnings.score=1.01,d=>d.earnings.coverage=10,d=>d.earnings.asof='2026-09-01',d=>d.model_version='3.12-evidence-first-1',d=>d.nifty.date='2026-02-30']){
  const d=fixture();mutate(d);assert(!M.calculate(d,now).allocationReady);
 }
});
test('trend verification reconstructs the average and rejects gaps, duplicates and partial months',()=>{
 assert(M.calculate(fixture(),now).allocationReady);
 for(const mutate of [d=>d.trend.monthly_closes.pop(),d=>d.trend.monthly_closes[9]=null,d=>d.trend.asof=20260831,d=>d.trend.monthly_closes[0].month='2025-12',d=>d.trend.monthly_closes[0].close+=100,d=>d.trend.monthly_closes[0].asof='2025-11-05',d=>d.trend.completed_month='2026-07']){
  const d=fixture();mutate(d);const r=M.calculate(d,now);assert(!r.allocationReady);assert(r.trendIssues.length>0);
 }
});
test('valuation anchors reconcile exactly when all price-dependent ratios are repriced',()=>{
 const d=fixture(),a=V.assess(d,now);assert(a);
 assert(a.anchors[0].index_level<a.anchors[1].index_level&&a.anchors[1].index_level<a.anchors[2].index_level);
 for(const x of a.anchors){const scale=x.index_level/d.nifty.level,n={...d.nifty,pe:d.nifty.pe*scale,pb:d.nifty.pb*scale,div_yield:d.nifty.div_yield/scale};assert(Math.abs(M.valuation(n,{...M.C,now}).z-x.z)<1e-8);}
 const eq=a.earnings_sensitivity.map(x=>x.equity_pct);for(let i=1;i<eq.length;i++)assert(eq[i]>=eq[i-1]);
});
test('background timer expires an individual daily input before packet expiry',()=>{
 const nodes=new Map(),node=id=>nodes.get(id)||nodes.set(id,{textContent:'',style:{},className:'',innerHTML:''}).get(id);
 let tick,time=Date.parse('2026-09-17T00:00:00Z');
 class Clock extends Date{constructor(...args){super(...(args.length?args:[time]));}static now(){return time;}}
 const c={AnupRobustness:{assess:()=>null},AnupHealth:require('../health.js'),document:{querySelector:node,querySelectorAll:()=>[]},Date:Clock,setInterval:f=>tick=f,AbortController,console,setTimeout:()=>0,clearTimeout(){},fetch:()=>new Promise(()=>{})};
 vm.createContext(c);vm.runInContext(fs.readFileSync(require.resolve('../model.js'),'utf8'),c);vm.runInContext(fs.readFileSync(require.resolve('../app.js'),'utf8'),c);
 const d=fixture();d.generated_at='2026-09-16T23:00:00Z';d.nifty.date='2026-09-16';d.nifty.gsec_meta.asof='2026-09-10';c.packet=d;
 vm.runInContext('render(packet)',c);assert.notEqual(node('#eq').textContent,'—');
 time=Date.parse('2026-09-18T00:00:01Z');tick();assert.equal(node('#eq').textContent,'—');
});
