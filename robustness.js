/* Scenario analysis, not forecast probabilities or optimized portfolio advice. */
(function(root){
'use strict';
const M=typeof module!=='undefined'&&module.exports?require('./model.js'):root.AnupModel;
function assess(d,now=new Date()){
 const r=M.calculate(d,now);if(!r.allocationReady)return null;
 const n=d.nifty,earn=d.earnings.score,macro=r.macroContextEligible?d.macro.score:null;
 const target=(z,k,zc,es,trendOff)=>{
  const damp=z<0?1:M.clip(1-Math.abs(z)/zc,0,1);
  const trendAdj=trendOff?-M.C.trendRiskOffPP:0;
  return M.clip(M.curve(z,k,zc)+es*M.C.earnMax*damp+trendAdj,0,100);
 };
 const shadowTarget=(z,k,zc,es,ms,trendOff)=>{
  const base=target(z,k,zc,es,trendOff),damp=z<0?1:M.clip(1-Math.abs(z)/zc,0,1);
  return M.clip(base+ms*M.C.macroShadowMax*damp,0,100);
 };
 const grid=[];for(const k of [.6,.8,1,1.15,1.35,1.5])for(const zc of [2.5,3,3.5,4])grid.push(target(r.z,k,zc,earn,r.trendRiskOff));
 const stress=[
  ['Current live inputs',r.final],
  ['Live earnings at maximum headwind',target(r.z,1.35,2.5,-1,r.trendRiskOff)],
  ['Trend risk-off + maximum live earnings headwind',target(r.z,1.35,2.5,-1,true)]
 ];
 if(macro!==null){
  stress.push(['Shadow only: macro at maximum headwind',shadowTarget(r.z,1.35,2.5,earn,-1,r.trendRiskOff)]);
  stress.push(['Shadow only: current macro context',shadowTarget(r.z,1.35,2.5,earn,macro,r.trendRiskOff)]);
 }
 const scenarios=[];for(const growth of [-5,5,10,15])for(const exitPE of [16,20,24]){
  const annual=100*((1+growth/100)*Math.pow(exitPE/n.pe,1/5)-1)+n.div_yield;
  scenarios.push({growth,exitPE,annual,excess:annual-n.gsec10});
 }
 return {min:Math.min(...grid),max:Math.max(...grid),stress,scenarios,macroAuthority:0,macroShadowAuthority:r.macroContextEligible?M.C.macroShadowMax*r.damp:0,trendAdjustment:r.ta,trendRiskOff:r.trendRiskOff};
}
const api={assess};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.AnupRobustness=api;
})(typeof window!=='undefined'?window:this);