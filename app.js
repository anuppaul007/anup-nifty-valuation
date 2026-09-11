'use strict';
const {calculate,band,clip,finite,fresh}=AnupModel;
const q=s=>document.querySelector(s);
const fmt=(x,d=2)=>finite(x)?x.toFixed(d):'—';
const signed=(x,d=1)=>finite(x)?(x>=0?'+':'')+x.toFixed(d):'—';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const stance=x=>!finite(x)?['not scored','warn']:x>.15?['supportive','good']:x<-.15?['headwind','bad']:['near neutral','warn'];
function clearAllocation(message){
 for(const id of ['eq','debt','pct','erp','core','eadj','madj','damp','final'])q('#'+id).textContent='—';
 q('#eqbar').style.width='0%';q('#barEq').textContent='Allocation withheld';q('#barDebt').textContent='';
 for(const id of ['lens','macroBlocks','macroDiag','market','earn','sources'])q('#'+id).innerHTML='';
 for(const id of ['mscore','mstance','mcov','vix','carry','conf'])q('#'+id).textContent='—';
 q('#confbar').style.width='0%';q('#pending').textContent='No current data have been verified.';
 q('#verdict').textContent=message;q('#status').textContent=message;q('#status').className='status bad';
}
function render(d){
 const r=calculate(d),n=d.nifty||{},m=d.macro||{},en=d.earnings||{};
 if(!r.valid){clearAllocation(r.reason);return;}
 const eq=r.allocationReady?Math.round(r.final):null,db=r.allocationReady?100-eq:null;
 q('#eq').textContent=r.allocationReady?eq+'%':'—';q('#debt').textContent=r.allocationReady?db+'%':'—';q('#pct').textContent=signed(r.z,2);q('#erp').textContent=Math.round(r.fundamentalCoverage*100)+'%';
 q('#eqbar').style.width=(eq||0)+'%';q('#barEq').textContent=r.allocationReady?'Equity '+eq+'%':'Complete-data gate active';q('#barDebt').textContent=r.allocationReady?'Debt '+db+'%':'';
 q('#verdict').textContent=r.allocationReady?`Valuation is ${band(r.z)} against the model’s fixed references. With every required macro block verified, the strategic model target is ${r.final.toFixed(1)}% equity / ${(100-r.final).toFixed(1)}% debt. This is a research allocation rule; the macro influence cap is not yet return-optimized by walk-forward backtesting.`:`No equity/debt target is published because ${r.holdReason||'the complete-data gate is not satisfied'}. Fundamental valuation is still shown, but the website will not convert incomplete macro evidence into a precise allocation.`;
 q('#lens').innerHTML=r.L.map(x=>`<tr><td>${esc(x.label)}</td><td>${fmt(x.now)}</td><td>${fmt(x.reference)}</td><td>${signed(x.z,2)}</td><td>${x.weight.toFixed(1)}%</td></tr>`).join('');
 q('#core').textContent=fmt(r.core,1)+'%';q('#eadj').textContent=r.earningsComplete?signed(r.ea,2)+' pp':'Withheld';q('#madj').textContent=r.macroEligible?signed(r.ma,2)+' pp':'Withheld';q('#damp').textContent=fmt(100*r.damp,0)+'%';q('#final').textContent=r.allocationReady?fmt(r.final,1)+'%':'Withheld';
 q('#overlayNote').textContent=r.allocationReady?`Macro adjustment = verified macro score × 6 pp × ${(100*r.damp).toFixed(1)}% valuation damping. Coverage is 100%; no missing factor is neutral-filled.`:`Complete-data rule: final allocation requires 100% verified macro coverage plus current earnings and India bond data. Current verified macro coverage is ${(100*r.coverage).toFixed(1)}%.`;
 const names={global_liquidity:'Global liquidity',india_external_carry:'India external / carry',china_industrial:'China industrial cycle',relative_em_valuation:'EM ex-India large-cap relative valuation'},details=m.block_weight_detail||{};
 const blockRows=Object.entries(names).filter(([k])=>finite(m.blocks?.[k])&&(details[k]?.internal_coverage||0)>=.999).map(([k,label])=>{const v=m.blocks[k],a=details[k]||{},st=stance(v);return `<tr><td>${label}</td><td class="${st[1]}">${signed(v,2)}</td><td>${fmt(100*(a.strategic_weight||0),0)}%</td><td>100%</td><td>${fmt(100*(a.effective_weight||0),1)}%</td><td>${st[0]}</td></tr>`;});
 q('#macroBlocks').innerHTML=blockRows.length?blockRows.join(''):'<tr><td colspan="6" class="left">No macro block is published until its internal data are fully verified.</td></tr>';
 const ch=m.china_pmi||{},em=m.relative_em||{},factors=m.factors||{},packetOk=d.schema_version===4&&fresh(d.generated_at,3);
 const defs=[['US 10Y real yield','us_real_10y','%'],['US nominal 10Y','us_10y','%'],['India − US 10Y spread','india_us_10y_spread',' pp'],['Broad USD, ~3 months','usd_3m_pct','%'],['Brent futures, 63 observations','brent_3m_pct','%'],['Fed assets, 26 observations','fed_assets_6m_pct','%'],['VIX','vix',''],['India broad REER','india_reer_bis',''],['USD/INR, ~3 months','usd_inr_3m_pct','%']];
 const rows=defs.flatMap(([label,key,unit])=>{const f=factors[key]||{};return f.status==='live'&&finite(m[key])?[[label,fmt(m[key])+unit,f.asof||'','verified']]:[];});
 if(ch.status==='live'&&finite(ch.pmi))rows.push(['China manufacturing PMI',fmt(ch.pmi,1),ch.asof||'','verified']);
 if(ch.status==='live'&&finite(ch.new_orders))rows.push(['China new orders',fmt(ch.new_orders,1),ch.asof||'','verified']);
 if(em.status==='live'&&finite(em.em_ex_india_pe))rows.push(['EM ex-India large-cap trailing P/E',fmt(em.em_ex_india_pe,1)+'×',em.asof||'','verified']);
 if(em.status==='live'&&finite(em.em_ex_india_pb))rows.push(['EM ex-India large-cap P/B',fmt(em.em_ex_india_pb,1)+'×',em.asof||'','verified']);
 q('#macroDiag').innerHTML=rows.length?rows.map(row=>`<tr>${row.map(v=>`<td>${esc(v)}</td>`).join('')}</tr>`).join(''):'<tr><td colspan="4" class="left">Verified macro observations are temporarily unavailable; no target is published.</td></tr>';
 const requiredFactorNames={us_real_10y:'US real yield',usd_3m_pct:'broad USD',fed_assets_6m_pct:'Fed assets',vix:'VIX',brent_3m_pct:'Brent',india_us_10y_spread:'India-US carry',india_reer_bis:'India REER',usd_inr_3m_pct:'USD/INR'};
 const issues=Object.entries(requiredFactorNames).filter(([k])=>factors[k]?.status!=='live').map(([,v])=>v);
 if(ch.status!=='live')issues.push('China PMI');if(em.status!=='live')issues.push('EM ex-India valuation history');
 q('#pending').className='flag '+(r.allocationReady?'good':'bad');
 q('#pending').textContent=r.allocationReady?'Complete-data gate passed: all planned macro blocks are verified and scored.':`Allocation withheld. ${issues.length?`Required inputs not yet eligible: ${issues.join(', ')}. `:''}No missing, stale, cached or pending-history value is displayed as a scored input.`;
 const gm=n.gsec_meta||{};
 q('#market').innerHTML=[['NIFTY 50',n.level.toLocaleString('en-IN')],['P/E',fmt(n.pe)],['P/B',fmt(n.pb)],['Dividend yield',fmt(n.div_yield)+'%'],['NIFTY date',n.date],['India ~10Y',fmt(n.gsec10)+'%'],['India yield date',gm.asof||'Not verified'],['India yield instrument',gm.security||gm.source||'Not verified']].map(x=>`<div>${esc(x[0])}</div><div>${esc(x[1])}</div>`).join('');
 q('#earn').innerHTML=[['Index-implied EPS',fmt(en.eps,1)],['Cycle observation date',en.asof||'Not verified'],['EPS growth, 12 months',signed(en.eps_growth_12m)+'%'],['Growth acceleration, 6 months',signed(en.acceleration_6m)+' pp'],['Earnings score',r.earningsComplete?signed(en.score,2):'Withheld']].map(x=>`<div>${esc(x[0])}</div><div>${esc(x[1])}</div>`).join('');
 const score=r.macroEligible?m.score:null,st=stance(score);q('#mscore').textContent=r.macroEligible?signed(score,2):'Withheld';q('#mstance').textContent=r.macroEligible?st[0]:'complete data required';q('#mcov').textContent=fmt(100*r.coverage,0)+'%';q('#vix').textContent=factors.vix?.status==='live'?fmt(m.vix,1):'—';q('#carry').textContent=factors.india_us_10y_spread?.status==='live'?fmt(m.india_us_10y_spread)+' pp':'—';
 const qualityOk=packetOk&&factors.vix?.status==='live'&&finite(d.confidence);q('#confbar').style.width=(qualityOk?clip(d.confidence,0,1)*100:0)+'%';q('#conf').textContent=qualityOk?`${fmt(d.confidence*100,0)}/100 data/stress indicator — heuristic, not probability of profit.`:'Data/stress indicator withheld until current dated inputs are available.';
 q('#sources').innerHTML=(d.sources||[]).map(s=>`<p><b>${esc(s.name)}</b><br>${esc(s.role)}${s.url&&/^https:\/\//.test(s.url)?`<br><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">Source</a>`:''}</p>`).join('');
 const old=!packetOk;q('#status').textContent=`${old?'Old published file — target withheld':'Published data'} · NIFTY ${n.date} · refresh ${new Date(d.generated_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})} IST`;q('#status').className='status '+(old?'bad':r.allocationReady?'good':'warn');
}
let requestNumber=0;
async function loadData(){
 const request=++requestNumber,controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);q('#status').textContent='Checking latest published data…';
 try{
  const urls=['https://api.github.com/repos/anuppaul007/anup-nifty-valuation/contents/data/latest.json','https://raw.githubusercontent.com/anuppaul007/anup-nifty-valuation/main/data/latest.json'];let d,lastError;
  for(const url of urls){try{const response=await fetch(url+'?t='+Date.now(),{cache:'no-store',signal:controller.signal,headers:{Accept:'application/vnd.github.raw+json'}});if(!response.ok)throw Error('HTTP '+response.status);const payload=await response.json();d=payload.encoding==='base64'&&typeof payload.content==='string'?JSON.parse(atob(payload.content)):payload;if(!d.nifty)throw Error('Unexpected published data format');break;}catch(error){lastError=error;}}
  if(!d)throw lastError||Error('Data unavailable');if(request===requestNumber)render(d);
 }catch(error){if(request===requestNumber)clearAllocation('Published data could not be loaded. Allocation is withheld; please try again later.');}
 finally{clearTimeout(timer);}
}
loadData();
