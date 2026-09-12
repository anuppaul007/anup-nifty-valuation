/* Scenario analysis, not forecast probabilities or optimized portfolio advice. */
(function(root){
'use strict';
const M=typeof module!=='undefined'&&module.exports?require('./model.js'):root.AnupModel;
function assess(d,now=new Date()){
 const r=M.calculate(d,now);if(!r.allocationReady)return null;
 const n=d.nifty,earn=d.earnings.score,macro=d.macro.score;
 const target=(z,k,zc,es,ms)=>M.clip(M.curve(z,k,zc)+(es*M.C.earnMax+ms*M.C.macroMax)*M.clip(1-Math.abs(z)/zc,0,1),0,100);
 const grid=[];for(const k of [.6,.8,1,1.15,1.35,1.5])for(const zc of [2.5,3,3.5,4])grid.push(target(r.z,k,zc,earn,macro));
 const stress=[['Current inputs',r.final],['All macro blocks at maximum headwind',target(r.z,1.35,2.5,earn,-1)],['Macro and earnings at maximum headwind',target(r.z,1.35,2.5,-1,-1)]];
 const scenarios=[];for(const growth of [-5,5,10,15])for(const exitPE of [16,20,24]){
  const annual=100*((1+growth/100)*Math.pow(exitPE/n.pe,1/5)-1)+n.div_yield;
  scenarios.push({growth,exitPE,annual,excess:annual-n.gsec10});
 }
 return {min:Math.min(...grid),max:Math.max(...grid),stress,scenarios,macroAuthority:M.C.macroMax*r.damp};
}
const api={assess};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.AnupRobustness=api;
})(typeof window!=='undefined'?window:this);
