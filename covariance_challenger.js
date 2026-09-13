/* Research shadow only. Zero live allocation authority. */
(function(root){
'use strict';
const M=typeof module!=='undefined'&&module.exports?require('./model.js'):root.AnupModel;
const VERSION='covariance-shrinkage-consensus-v1';
const LABELS=Object.freeze(['pe_z','pb_log_profitability_z','earnings_yield_minus_gsec_z','dividend_yield_z']);
const WEIGHTS=Object.freeze([0.2201625077,0.2073700218,0.2668621038,0.3056053667]);
function compute(d,now=new Date()){
  const base=M.calculate(d,now);
  if(!base.valid)return{version:VERSION,valid:false,allocationReady:false,reason:base.reason,live_authority:false};
  if(!Array.isArray(base.L)||base.L.length!==4||base.L.some(x=>!M.finite(x.z)))return{version:VERSION,valid:false,allocationReady:false,reason:'All four V3.13 valuation lenses are required for the challenger.',live_authority:false};
  const z=base.L.reduce((a,x,i)=>a+x.z*WEIGHTS[i],0);
  const core=M.curve(z);
  const ea=base.earningsComplete?M.clip(d.earnings.score,-1,1)*M.C.earnMax*M.overlayDamp(z):0;
  const ta=base.trendRiskOff?-M.C.trendRiskOffPP:0;
  const final=base.allocationReady?M.clip(core+ea+ta,0,100):null;
  return{
    version:VERSION,
    base_model_version:M.VERSION,
    valid:true,
    allocationReady:base.allocationReady,
    holdReason:base.holdReason,
    labels:LABELS,
    weights:WEIGHTS,
    z,
    core,
    earnings_adjustment:ea,
    trend_adjustment:ta,
    final,
    live_core:base.core,
    live_final:base.final,
    difference_vs_live_pp:final===null||base.final===null?null:final-base.final,
    live_authority:false,
    interpretation:'Preregistered covariance-shrinkage research shadow. It cannot change the live allocation.'
  };
}
const api={VERSION,LABELS,WEIGHTS,compute};
if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.AnupCovarianceChallenger=api;
})(typeof window!=='undefined'?window:this);
