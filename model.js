/* Fixed-reference research model. Parameters are assumptions, not optimized weights. */
(function(root){
'use strict';
const C=Object.freeze({peM:22.44,peS:2.08,pbM:3.88,pbS:.45,roeM:17.36,roeS:1.92,dyM:1.25,dyS:.18,gapM:-2.60,gapS:.70,wPE:30,wPB:25,wGAP:30,wDY:10,beta:.60,k:1.35,zc:2.5,macroMax:6,earnMax:6,minMacroCoverage:.999});
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const clip=(x,a,b)=>Math.max(a,Math.min(b,x));
function ageDays(s,now=new Date()){
 if(typeof s!=='string'||!/^\d{4}-\d{2}-\d{2}/.test(s))return Infinity;
 const t=Date.parse(s);return Number.isFinite(t)?(now.getTime()-t)/86400000:Infinity;
}
const fresh=(s,days,now)=>{const age=ageDays(s,now);return age>=0&&age<=days;};
function curve(z){const f=x=>100/(1+Math.exp(C.k*x)),lo=f(C.zc),hi=f(-C.zc);return clip((f(z)-lo)/(hi-lo)*100,0,100);}
function calculate(d,now=new Date()){
 const n=d?.nifty;
 if(!n||['level','pe','pb','div_yield'].some(k=>!finite(n[k])||n[k]<=0))return{valid:false,reason:'Missing or invalid NIFTY valuation inputs.'};
 if(!fresh(n.date,7,now))return{valid:false,reason:'NIFTY observation date is stale, missing, or in the future. Allocation is withheld.'};
 const gm=n.gsec_meta||{},gOK=finite(n.gsec10)&&n.gsec10>0&&gm.status!=='excluded'&&fresh(gm.asof,gm.max_age_days||7,now);
 const gap=gOK?100/n.pe-n.gsec10:null,roe=100*n.pb/n.pe;
 const L=[
  {label:'Trailing P/E',now:n.pe,reference:C.peM,z:(n.pe-C.peM)/C.peS,planned:C.wPE},
  {label:'P/B, implied-profitability adjustment',now:n.pb,reference:C.pbM,z:(n.pb-C.pbM)/C.pbS-C.beta*(roe-C.roeM)/C.roeS,planned:C.wPB},
  {label:'Earnings yield − G-sec',now:gap,reference:C.gapM,z:gOK?-(gap-C.gapM)/C.gapS:null,planned:C.wGAP},
  {label:'Dividend yield',now:n.div_yield,reference:C.dyM,z:-(n.div_yield-C.dyM)/C.dyS,planned:C.wDY}
 ];
 const total=L.reduce((a,x)=>a+x.planned,0),used=L.filter(x=>finite(x.z)).reduce((a,x)=>a+x.planned,0);
 L.forEach(x=>x.weight=finite(x.z)?100*x.planned/used:0);
 const z=L.reduce((a,x)=>a+(finite(x.z)?x.z*x.weight/100:0),0),core=curve(z),damp=clip(1-Math.abs(z)/C.zc,0,1);
 const m=d.macro||{},en=d.earnings||{},packetFresh=fresh(d.generated_at,3,now);
 const macroPacketValid=d.schema_version===4&&packetFresh&&!d.macro_stale&&finite(m.score)&&finite(m.active_block_weight);
 const coverage=macroPacketValid?clip(m.active_block_weight,0,1):0;
 const macroEligible=macroPacketValid&&coverage>=C.minMacroCoverage;
 const earningsEligible=d.schema_version===4&&packetFresh&&finite(en.score)&&fresh(en.asof,70,now);
 const earnCoverage=earningsEligible&&finite(en.coverage)?clip(en.coverage,0,1):0;
 const earningsComplete=earningsEligible&&earnCoverage>=.999;
 const ea=earningsComplete?clip(en.score,-1,1)*C.earnMax*damp:0;
 // A final target is never computed from a partial macro engine. No missing value is neutral-filled.
 const ma=macroEligible?clip(m.score,-1,1)*C.macroMax*damp:0;
 const allocationReady=gOK&&macroEligible&&earningsComplete;
 let holdReason=null;
 if(!gOK)holdReason='current dated India ~10Y yield unavailable';
 else if(!macroPacketValid)holdReason='macro packet is stale or invalid';
 else if(!macroEligible)holdReason=`verified macro coverage ${(100*coverage).toFixed(1)}% is below the 100% requirement`;
 else if(!earningsComplete)holdReason='earnings-cycle history is incomplete or stale';
 return{valid:true,allocationReady,L,z,core,damp,ea,ma,final:allocationReady?clip(core+ea+ma,0,100):null,coverage,earnCoverage,macroEligible,macroPacketValid,earningsEligible,earningsComplete,gsecEligible:gOK,fundamentalCoverage:used/total,holdReason};
}
function band(z){if(z<=-2.5)return'extremely low';if(z<-.674)return'low';if(z<-.126)return'below reference';if(z<.126)return'near reference';if(z<.674)return'above reference';if(z<2.5)return'high';return'extremely high';}
const api={C,finite,clip,ageDays,fresh,curve,calculate,band};
if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.AnupModel=api;
})(typeof window!=='undefined'?window:this);
