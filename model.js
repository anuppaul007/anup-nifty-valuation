/* V3.13: monotone P/B valuation, reconstructed trend evidence and strict daily
 * source gates. Macro remains context/shadow only. This is a prospective
 * structural repair, not a validated performance improvement. */
(function(root){
'use strict';
const C=Object.freeze({peM:22.44,peS:2.08,pbM:3.54,pbS:0.3239941700435707,roeM:16.15402934929392,roeS:0.9884905234449538,dyM:1.25,dyS:.18,gapM:-2.60,gapS:.70,wPE:30,wPB:25,wGAP:30,wDY:10,beta:.60,k:1.35,zc:2.5,macroMax:0,macroShadowMax:6,earnMax:6,trendRiskOffPP:20,minMacroCoverage:.999,macroRequiredWeight:1.0});
const finite=x=>typeof x==='number'&&Number.isFinite(x);
// Frozen on the same 36 current-definition observations as V3.10. This is
// a monotonicity repair, not a return-optimized calibration.
const PB_LOG=Object.freeze({offset:0.0031695843111495,scale:0.062405429030436874});
const clip=(x,a,b)=>Math.max(a,Math.min(b,x));
function ageDays(s,now=new Date()){
 if(typeof s!=='string'||!/^\d{4}-\d{2}-\d{2}/.test(s))return Infinity;
 const day=s.slice(0,10),parsed=new Date(day+'T00:00:00Z');
 if(!Number.isFinite(parsed.getTime())||parsed.toISOString().slice(0,10)!==day)return Infinity;
 const t=Date.parse(s);return Number.isFinite(t)?(now.getTime()-t)/86400000:Infinity;
}
const fresh=(s,days,now)=>{const age=ageDays(s,now);return age>=0&&age<=days;};
const previousMonth=now=>new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),0)).toISOString().slice(0,7);
function pbZ(pe,pb){return (Math.log(pb/C.pbM)-C.beta*Math.log((100*pb/pe)/C.roeM)-PB_LOG.offset)/PB_LOG.scale;}
function valuation(n,params=C){
 const gm=n.gsec_meta||{},gOK=finite(n.gsec10)&&n.gsec10>0&&gm.status==='live'&&fresh(gm.asof,7,params.now||new Date());
 const gap=gOK?100/n.pe-n.gsec10:null;
 const L=[
  {label:'Trailing P/E',now:n.pe,reference:params.peM,z:(n.pe-params.peM)/C.peS,planned:C.wPE},
  {label:'P/B, log profitability adjustment',now:n.pb,reference:C.pbM,z:pbZ(n.pe,n.pb),planned:C.wPB},
  {label:'Earnings yield − G-sec',now:gap,reference:C.gapM,z:gOK?-(gap-C.gapM)/C.gapS:null,planned:C.wGAP},
  {label:'Dividend yield',now:n.div_yield,reference:C.dyM,z:-(n.div_yield-C.dyM)/C.dyS,planned:C.wDY}
 ];
 const total=L.reduce((a,x)=>a+x.planned,0),used=L.filter(x=>finite(x.z)).reduce((a,x)=>a+x.planned,0);
 L.forEach(x=>x.weight=finite(x.z)?100*x.planned/used:0);
 const z=L.reduce((a,x)=>a+(finite(x.z)?x.z*x.weight/100:0),0);
 return {L,z,core:curve(z),gOK,total,used};
}
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
 if(t?.completed_month!==previousMonth(now)||typeof t?.asof!=='string'||t.asof.slice(0,7)!==t.completed_month)issues.push('trend_completed_month');
 const rows=t?.monthly_closes;
 if(!Array.isArray(rows)||rows.length!==10)issues.push('trend_source_rows');
 else {
  const expectedEnd=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),1));
  let sum=0;
  rows.forEach((r,i)=>{
   if(!r||typeof r!=='object'){issues.push('trend_row_'+i);return;}
   const month=new Date(Date.UTC(expectedEnd.getUTCFullYear(),expectedEnd.getUTCMonth()-10+i,1)).toISOString().slice(0,7);
   if(r.month!==month||typeof r.asof!=='string'||r.asof.slice(0,7)!==month||!Number.isFinite(ageDays(r.asof,now))||!finite(r.close)||r.close<=0)issues.push('trend_row_'+i);
   // A partial-month response must not masquerade as a completed close.
   const monthEnd=new Date(Date.UTC(Number(month.slice(0,4)),Number(month.slice(5,7)),0));
   if(!fresh(r.asof,7,monthEnd))issues.push('trend_partial_month_'+i);
   sum+=r.close;
  });
  if(Math.abs(sum/10-t.sma10)>1e-7||rows[9]?.close!==t.completed_month_close||rows[9]?.asof!==t.asof)issues.push('trend_reconstruction');
 }
 if(typeof t?.risk_off!=='boolean')issues.push('trend_flag');
 if(finite(t?.completed_month_close)&&finite(t?.sma10)&&typeof t?.risk_off==='boolean'&&t.risk_off!==(t.completed_month_close<t.sma10))issues.push('trend_flag_mismatch');
 return issues;
}
function calculate(d,now=new Date()){
 if(d?.schema_version!==4||d?.model_version!==VERSION)return {valid:false,reason:'Published model version does not match this engine. Reload to receive a consistent release; allocation is withheld.'};
 const n=d?.nifty;
 if(!n||['level','pe','pb','div_yield'].some(k=>!finite(n[k])||n[k]<=0))return{valid:false,reason:'Missing or invalid NIFTY valuation inputs.'};
 if(!fresh(n.date,7,now))return{valid:false,reason:'NIFTY observation date is stale, missing, or in the future. Allocation is withheld.'};
 const {L,z,core,gOK,total,used}=valuation(n,{...C,now}),damp=overlayDamp(z);
 const m=d.macro||{},en=d.earnings||{},t=d.trend||{},packetFresh=fresh(d.generated_at,3,now);
 const macroIssues=verifyMacro(m,now),trendIssues=verifyTrend(t,now);
 const macroPacketValid=d.schema_version===4&&packetFresh&&!d.macro_stale&&finite(m.score)&&finite(m.active_block_weight)&&macroIssues.length===0;
 const coverage=macroPacketValid?clip(m.active_block_weight/C.macroRequiredWeight,0,1):0;
 const macroEligible=macroPacketValid&&coverage>=C.minMacroCoverage;
 const earningsEligible=d.schema_version===4&&packetFresh&&finite(en.score)&&Math.abs(en.score)<=1&&finite(en.coverage)&&en.coverage>=0&&en.coverage<=1&&fresh(en.asof,45,now)&&en.asof.slice(0,7)===previousMonth(now);
 const earnCoverage=earningsEligible&&finite(en.coverage)?clip(en.coverage,0,1):0;
 const earningsComplete=earningsEligible&&earnCoverage>=.999;
 const trendEligible=d.schema_version===4&&packetFresh&&trendIssues.length===0;
 const ea=earningsComplete?clip(en.score,-1,1)*C.earnMax*damp:0;
 const ma=0;
 const macroShadowAdjustment=macroEligible?clip(m.score,-1,1)*C.macroShadowMax*damp:null;
 const trendRiskOff=trendEligible&&t.risk_off===true;
 const ta=trendRiskOff?-C.trendRiskOffPP:0;
 const allocationReady=gOK&&earningsComplete&&trendEligible;
 let holdReason=null;
 if(!gOK)holdReason='current dated India ~10Y yield unavailable';
 else if(!earningsComplete)holdReason='earnings-cycle history is incomplete or stale';
 else if(!trendEligible)holdReason='trend crash-guard input is stale, incomplete or inconsistent'+(trendIssues.length?': '+trendIssues.join(', '):'');
 return{model_version:VERSION,valid:true,allocationReady,L,z,core,damp,ea,ma,macroShadowAdjustment,macroLiveAuthority:false,macroContextEligible:macroEligible,ta,trendEligible,trendRiskOff,trendIssues,final:allocationReady?clip(core+ea+ta,0,100):null,coverage,earnCoverage,macroEligible,macroPacketValid,earningsEligible,earningsComplete,macroIssues,gsecEligible:gOK,fundamentalCoverage:used/total,holdReason};
}
function band(z){if(z<=-2.5)return'extremely low';if(z<-.674)return'low';if(z<-.126)return'below reference';if(z<.126)return'near reference';if(z<.674)return'above reference';if(z<2.5)return'high';return'extremely high';}
const VERSION='3.13-reliability-1';
const api={VERSION,C,PB_LOG,FACTORS,verifyMacro,verifyTrend,finite,clip,ageDays,fresh,previousMonth,pbZ,valuation,curve,overlayDamp,calculate,band};
if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.AnupModel=api;
})(typeof window!=='undefined'?window:this);
