/* Research-only crash-guard candidate. Does not alter the live allocator.
 *
 * Rationale: the current live model multiplies macro authority by a symmetric
 * extreme-valuation damping factor. At very cheap valuation extremes that can
 * drive macro authority to zero, allowing severe macro stress to coexist with
 * a 100% equity signal.
 *
 * This candidate deliberately does the opposite on the cheap side:
 *   - cheap side (z < 0): retain full macro authority;
 *   - expensive side (z >= 0): retain the current valuation damping.
 *
 * That direction is intentional. Damping macro to zero at the cheap endpoint
 * would preserve, not fix, the crash-resistance defect.
 */
(function(root){
'use strict';

const Base = (typeof require==='function') ? require('./model.js') : root.AnupModel;
if(!Base) throw new Error('AnupModel is required');

function macroDamp(z,currentDamp){
  if(!Base.finite(z)||!Base.finite(currentDamp)) return null;
  return z < 0 ? 1 : Base.clip(currentDamp,0,1);
}

function applyToBaseResult(baseResult,macroScore){
  if(!baseResult||!baseResult.valid) return {valid:false,reason:'Invalid base-model result'};
  const md=macroDamp(baseResult.z,baseResult.damp);
  if(!Base.finite(md)) return {valid:false,reason:'Invalid macro damping inputs'};
  const score=Base.finite(macroScore)?Base.clip(macroScore,-1,1):null;
  const macroAdjustment=(baseResult.allocationReady&&score!==null)?score*Base.C.macroMax*md:0;
  const final=baseResult.allocationReady?Base.clip(baseResult.core+baseResult.ea+macroAdjustment,0,100):null;
  return {
    valid:true,
    research_only:true,
    candidate_id:'asymmetric-macro-authority-v1',
    allocationReady:baseResult.allocationReady,
    z:baseResult.z,
    core:baseResult.core,
    earningsAdjustment:baseResult.ea,
    currentSymmetricDamp:baseResult.damp,
    candidateMacroDamp:md,
    macroScore:score,
    candidateMacroAdjustment:macroAdjustment,
    currentFinal:baseResult.final,
    candidateFinal:final,
    candidateDebt:Base.finite(final)?100-final:null,
    governance:'Research challenger only; not eligible for automatic live promotion.'
  };
}

function calculate(packet,now=new Date()){
  const base=Base.calculate(packet,now);
  const score=packet?.macro?.score;
  return applyToBaseResult(base,score);
}

const api={macroDamp,applyToBaseResult,calculate};
if(typeof module!=='undefined'&&module.exports) module.exports=api;
else root.AnupMacroGuardCandidate=api;
})(typeof window!=='undefined'?window:this);
