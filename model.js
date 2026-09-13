/* V3.11: crash-aware live allocation.
 * Valuation references, curve slope and extreme threshold remain unchanged from V3.10.
 * Cheap-side macro/earnings authority is retained, and the frozen SMA10-minus20 rule
 * is promoted as a one-way risk-off brake. See LIVE_V3_11_DECISION.md. */
(function(root){
'use strict';
const C=Object.freeze({peM:22.44,peS:2.08,pbM:3.54,pbS:0.3239941700435707,roeM:16.15402934929392,roeS:0.9884905234449538,dyM:1.25,dyS:.18,gapM:-2.60,gapS:.70,wPE:30,wPB:25,wGAP:30,wDY:10,beta:.60,k:1.35,zc:2.5,macroMax:6,earnMax:6,trendRiskOffPP:20,minMacroCoverage:.999,macroRequiredWeight:1.0});
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const clip=(x,a,b)=>Math.max(a,Math.min(b,x));
function ageDays(s,now=new Date()){
 if(typeof s!=='string'||!/^\d{4}-\d{2}-\d{2}/.test(s))return Infinity;
 const t=Date.parse(s);return Number.isFinite(t)?(now.getTime()-t)/86400000:Infinity;
}
const fresh=(s,days,now)=>{const age=ageDays(s,now);return age>=0&&age<=days;};
function curve(z,k=C.k,zc=C.zc){const f=x=>100/(1+Math.exp(k*x)),lo=f(zc),hi=f(-zc);return clip((f(z)-lo)/(hi-lo)*100,0,100);}
function overlayDamp(z,zc=C.zc){return z<0?1:clip(1-Math.abs(z)/zc,0,1);}
const FACTORS=Object.freeze({us_real_10y:[7,.30*.40],fed_assets_6m_pct:[15,.30*.25],usd_3m_pct:[75,.30*.20],vix:[7,.30*.15],brent_3m_pct:[7,.25*.30],india_us_10y_spread:[7,.25*.25],india_reer_bis:[100,.25*.25],usd_inr_3m_pct:[75,.25*.20]});
function verifyMacro(m,now){
 const issues=[];let reconstructed=0;
 for(const [key,[days,weight]] of Object.entries(FACTORS)){
  const f=m.factors?.[key];
  if(!f||f.display_only===true||f.status!=='live'||!finite(f.value)||!finite(f.score)||Math.abs(f.score)>1||!fresh(f.asof,days,now))issues.push(key);
  else reconstructed+=weight*f.score;
 }
 const ch=m.china_pmi;
 if(!ch||ch.status!=='live'||ch.coverage<.999||!finite(ch.pmi)||!finite(ch.new_orders)||!finite(ch.score)||Math.abs(ch.score)>1||!fresh(ch.asof,70,now))issues.push('china_pmi');
 else reconstructed+=.20*ch.score;
 const dom=m.domestic;
 if(!dom||dom.status!=='live'||dom.coverage<.999||!finite(dom.score)||Math.abs(dom.score)>1)issues.push('india_domestic');
 else {
  let subtotal=0;
  for(const [key,days,weight] of [['india_cpi_yoy',75,.4],['india_iip_yoy',90,.35],['india_repo_rate',7,.25]]){
   const f=dom.factors?.[key];
   if(!f||f.display_only===true||f.status!=='live'||!finite(f.value)||!finite(f.score)||Math.abs(f.score)>1||!fresh(f.asof,days,now))issues.push(key);
   else subtotal+=f.score*weight;
  }
  if(Math.abs(subtotal-dom.score)>1e-8)issues.push('domestic_score_mismatch');
  reconstructed+=.25*dom.score;
 }
 if(!finite(m.score)||Math.abs(reconstructed-m.score)>1e-8)issues.push('macro_score_mismatch');
 return issues;
}
function verifyTrend(t,now){
 const issues=[];
 if(!t||t.status!=='live')issues.push('trend_status');
 if(t?.policy_id!=='trend-sma10-minus20-v1')issues.push('trend_policy');
 if(!finite(t?.completed_month_close)||t.completed_month_close<=0)issues.push('trend_close');
 if(!finite(t?.sma10)||t.sma10<=0)issues.push('trend_sma10');
 if(!fresh(t?.asof,45,now))issues.push('trend_asof');
 if(t?.lookback_months!==10)issues.push('trend_lookback');
 if(typeof t?.risk_off!=='boolean')issues.push('trend_flag');
 if(finite(t?.completed_month_close)&&finite(t?.sma10)&&typeof t?.risk_off==='boolean'&&t.risk_off!==(t.completed_month_close<t.sma10))issues.push('trend_flag_mismatch');
 return issues;
}
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
 const z=L.reduce((a,x)=>a+(finite(x.z)?x.z*x.weight/100:0),0),core=curve(z),damp=overlayDamp(z);
 const m=d.macro||{},en=d.earnings||{},t=d.trend||{},packetFresh=fresh(d.generated_at,3,now);
 const macroIssues=verifyMacro(m,now),trendIssues=verifyTrend(t,now);
 const macroPacketValid=d.schema_version===4&&packetFresh&&!d.macro_stale&&finite(m.score)&&finite(m.active_block_weight)&&macroIssues.length===0;
 const coverage=macroPacketValid?clip(m.active_block_weight/C.macroRequiredWeight,0,1):0;
 const macroEligible=macroPacketValid&&coverage>=C.minMacroCoverage;
 const earningsEligible=d.schema_version===4&&packetFresh&&finite(en.score)&&fresh(en.asof,70,now);
 const earnCoverage=earningsEligible&&finite(en.coverage)?clip(en.coverage,0,1):0;
 const earningsComplete=earningsEligible&&earnCoverage>=.999;
 const trendEligible=d.schema_version===4&&packetFresh&&trendIssues.length===0;
 const ea=earningsComplete?clip(en.score,-1,1)*C.earnMax*damp:0;
 const ma=macroEligible?clip(m.score,-1,1)*C.macroMax*damp:0;
 const trendRiskOff=trendEligible&&t.risk_off===true;
 const ta=trendRiskOff?-C.trendRiskOffPP:0;
 const allocationReady=gOK&&macroEligible&&earningsComplete&&trendEligible;
 let holdReason=null;
 if(!gOK)holdReason='current dated India ~10Y yield unavailable';
 else if(!macroPacketValid)holdReason='macro packet or individual observations are stale, incomplete or inconsistent'+(macroIssues.length?': '+macroIssues.join(', '):'');
 else if(!macroEligible)holdReason=`verified macro coverage ${(100*coverage).toFixed(1)}% is below the 100% requirement`;
 else if(!earningsComplete)holdReason='earnings-cycle history is incomplete or stale';
 else if(!trendEligible)holdReason='trend crash-guard input is stale, incomplete or inconsistent'+(trendIssues.length?': '+trendIssues.join(', '):'');
 return{model_version:VERSION,valid:true,allocationReady,L,z,core,damp,ea,ma,ta,trendEligible,trendRiskOff,trendIssues,final:allocationReady?clip(core+ea+ma+ta,0,100):null,coverage,earnCoverage,macroEligible,macroPacketValid,earningsEligible,earningsComplete,macroIssues,gsecEligible:gOK,fundamentalCoverage:used/total,holdReason};
}
function band(z){if(z<=-2.5)return'extremely low';if(z<-.674)return'low';if(z<-.126)return'below reference';if(z<.126)return'near reference';if(z<.674)return'above reference';if(z<2.5)return'high';return'extremely high';}
const VERSION='3.11-crash-aware-1';
const api={VERSION,C,FACTORS,verifyMacro,verifyTrend,finite,clip,ageDays,fresh,curve,overlayDamp,calculate,band};
if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.AnupModel=api;
})(typeof window!=='undefined'?window:this);