/* Research-only asymmetric macro-authority candidate.
 *
 * V3.12 gives macro zero live authority. This file is therefore retained only
 * as a historical/research challenger that applies the frozen ±6 pp SHADOW
 * macro budget. It does not alter the live allocator.
 *
 * Candidate logic:
 *   - cheap side (z < 0): retain full shadow macro authority;
 *   - expensive side (z >= 0): retain valuation damping.
 */
(function(root){
'use strict';

const Base = (typeof require==='function') ? require('./model.js') : root.AnupModel;
if(!Base) throw new Error('AnupModel is required');

function macroDamp(z,currentDamp){
  if(!Base.finite(z)||!Base.finite(currentDamp)) return null;
  return z < 0 ? 1 : Base.clip(currentDamp,0,1);
}

function shadowBudget(){
  return Base.finite(Base.C.macroShadowMax)?Base.C.macroShadowMax:Base.C.macroMax;
}

function applyToBaseResult(baseResult,macroScore){
  if(!baseResult||!baseResult.valid) return {valid:false,reason:'Invalid base-model result'};
  const md=macroDamp(baseResult.z,baseResult.damp);
  if(!Base.finite(md)) return {valid:false,reason:'Invalid macro damping inputs'};
  const score=Base.finite(macroScore)?Base.clip(macroScore,-1,1):null;
  const budget=shadowBudget();
  const macroAdjustment=(baseResult.allocationReady&&score!==null)?score*budget*md:0;
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
    candidateMacroBudget:budget,
    candidateMacroAdjustment:macroAdjustment,
    currentFinal:baseResult.final,
    candidateFinal:final,
    candidateDebt:Base.finite(final)?100-final:null,
    governance:'Research/shadow challenger only; V3.12 live macro authority is zero and this candidate is not eligible for automatic promotion.'
  };
}

function calculate(packet,now=new Date()){
  const base=Base.calculate(packet,now);
  const score=packet?.macro?.score;
  return applyToBaseResult(base,score);
}

const api={macroDamp,shadowBudget,applyToBaseResult,calculate};
if(typeof module!=='undefined'&&module.exports) module.exports=api;
else root.AnupMacroGuardCandidate=api;
})(typeof window!=='undefined'?window:this);
