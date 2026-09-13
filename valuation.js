/* Valuation sensitivity, never a confidence interval or trading forecast. */
(function(root){
'use strict';
const M=typeof module!=='undefined'&&module.exports?require('./model.js'):root.AnupModel;
function assess(d,now=new Date()){
 const r=M.calculate(d,now);if(!r.allocationReady)return null;
 const n=d.nifty;
 // Reprice all price-dependent ratios together, holding index-implied earnings,
 // book value, dividends and the government yield fixed. Repricing P/E alone
 // would contradict the same-index P/B and dividend-yield observations.
 const atScale=s=>M.valuation({...n,level:n.level*s,pe:n.pe*s,pb:n.pb*s,div_yield:n.div_yield/s},{...M.C,now});
 function solve(z){
  let lo=.01,hi=100;
  if(atScale(lo).z>z||atScale(hi).z<z)return null;
  for(let i=0;i<80;i++){const mid=(lo+hi)/2;if(atScale(mid).z<z)lo=mid;else hi=mid;}
  return n.level*(lo+hi)/2;
 }
 const policy=v=>M.clip(v.core+d.earnings.score*M.C.earnMax*M.overlayDamp(v.z)+r.ta,0,100);
 const anchors=[[-.674,'Below-reference boundary'],[0,'Model reference centre'],[.674,'Above-reference boundary']].map(([z,label])=>({label,z,index_level:solve(z)}));
 const references=[18,M.C.peM,26].map(peM=>{
  const v=M.valuation(n,{...M.C,peM,now});return {fair_pe:peM,equity_pct:policy(v),valuation_z:v.z};
 });
 const earningsShocks=[-20,-10,0,10].map(shock=>{
  const v=M.valuation({...n,pe:n.pe/(1+shock/100)},{...M.C,now});
  return {earnings_change_pct:shock,pe:n.pe/(1+shock/100),equity_pct:policy(v)};
 });
 return {model_version:M.VERSION,asof:n.date,anchors,reference_sensitivity:references,earnings_sensitivity:earningsShocks,
  drawdown_scenarios:[-20,-35,-50].map(eq=>({equity_return_pct:eq,debt_return_pct:0,portfolio_return_pct:r.final/100*eq})),
  assumptions:'Conditional on unchanged index-implied earnings, book value, dividends and bond yield. Reference boundaries are model conventions, not intrinsic-value estimates or statistical confidence intervals. Sensitivities hold the earnings overlay and trend regime fixed; they are not future signals.',
  independent_validation:'not_completed',timing_edge:'not_demonstrated'};
}
const api={assess};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.AnupValuation=api;
})(typeof window!=='undefined'?window:this);
