'use strict';
const {calculate,band,clip,ageDays,finite,fresh}=AnupModel;
const q=s=>document.querySelector(s);
const fmt=(x,d=2)=>finite(x)?x.toFixed(d):'—';
const signed=(x,d=1)=>finite(x)?(x>=0?'+':'')+x.toFixed(d):'—';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const stance=x=>!finite(x)?['excluded','warn']:x>.15?['supportive','good']:x<-.15?['headwind','bad']:['near neutral','warn'];
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
 q('#eqbar').style.width=(eq||0)+'%';q('#barEq').textContent=r.allocationReady?'Equity '+eq+'%':'Allocation withheld';q('#barDebt').textContent=r.allocationReady?'Debt '+db+'%':'';
 q('#verdict').textContent=r.allocationReady?`Valuation is ${band(r.z)} against this model’s fixed references. The model target is ${r.final.toFixed(1)}% equity / ${(100-r.final).toFixed(1)}% debt${r.provisional?' (provisional: incomplete optional inputs)':''}. This is a research rule, not a return-maximizing allocation established by backtesting.`:'Allocation is withheld because a sufficiently recent, dated India bond yield is unavailable. The remaining valuation lenses are shown for reference; they do not establish an equity/debt target.';
 q('#lens').innerHTML=r.L.map(x=>`<tr><td>${esc(x.label)}</td><td>${fmt(x.now)}</td><td>${fmt(x.reference)}</td><td>${signed(x.z,2)}</td><td>${x.weight.toFixed(1)}%</td></tr>`).join('');
 for(const [id,value] of [['core',fmt(r.core,1)+'%'],['eadj',r.earningsEligible?signed(r.ea,2)+' pp':'Excluded'],['madj',r.macroEligible?signed(r.ma,2)+' pp':'Excluded'],['damp',fmt(100*r.damp,0)+'%'],['final',fmt(r.final,1)+'%']])q('#'+id).textContent=r.allocationReady?value:'Withheld';
 q('#overlayNote').textContent=`Macro adjustment = available-factor score × 6 pp × ${(100*r.coverage).toFixed(1)}% coverage × ${(100*r.damp).toFixed(1)}% valuation damping. Both overlays vanish at z ≤ −2.5 or z ≥ +2.5. Missing scores remain excluded.`;
 const names={global_liquidity:'Global liquidity',india_external_carry:'India external / carry',china_industrial:'China industrial cycle',relative_em_valuation:'EM ex-India relative valuation'};
 const details=m.block_weight_detail||{};
 q('#macroBlocks').innerHTML=Object.entries(names).map(([k,label])=>{const v=r.macroEligible?m.blocks?.[k]:null,a=details[k]||{},st=stance(v);return `<tr><td>${label}</td><td class="${st[1]}">${signed(v,2)}</td><td>${fmt(100*(a.strategic_weight||0),0)}%</td><td>${fmt(100*(a.internal_coverage||0),0)}%</td><td>${r.macroEligible?fmt(100*(a.effective_weight||0),1):'0.0'}%</td><td>${st[0]}</td></tr>`;}).join('');
 const ch=m.china_pmi||{},em=d.schema_version===4?(m.relative_em||{}):{},factors=m.factors||{},packetOk=d.schema_version===4&&fresh(d.generated_at,3);
 const rows=[['US 10Y real yield','us_real_10y','%'],['US nominal 10Y','us_10y','%'],['India − US 10Y spread','india_us_10y_spread',' pp'],['Broad USD, ~3 months','usd_3m_pct','%'],['Brent futures, 63 observations','brent_3m_pct','%'],['Fed assets, 26 observations','fed_assets_6m_pct','%'],['VIX','vix',''],['India REER','india_reer_bis',''],['USD/INR forward premium','forward_premium_1m','%']].map(([label,key,unit])=>{const f=factors[key]||{};return[label,finite(m[key])?fmt(m[key])+unit:'—',f.asof||'Date unknown',f.status||'legacy / excluded'];});
 rows.push(['China manufacturing PMI',fmt(ch.pmi,1),ch.asof||'Date unknown',ch.status||'excluded'],['China new orders',fmt(ch.new_orders,1),ch.asof||'Date unknown',finite(ch.new_orders)?ch.status||'excluded':'unavailable'],['EM trailing P/E (incl. losses)',fmt(em.em_ex_india_pe,1)+'×',em.asof||'Date unknown',em.status||'excluded'],['EM P/B',fmt(em.em_ex_india_pb,1)+'×',em.asof||'Date unknown',em.status||'excluded']);
 q('#macroDiag').innerHTML=rows.map(row=>`<tr>${row.map((v,i)=>`<td>${esc(i===3&&!packetOk?'Unverified file / excluded':v)}</td>`).join('')}</tr>`).join('');
 q('#pending').textContent=`Scoring coverage is ${(100*r.coverage).toFixed(1)}%. “Pending history”, stale, undated and unavailable factors receive no score. Cached values are identified separately. EM comparisons use the same source month; ${em.history_count||0} earlier validated months are available (12 required).`;
 const gm=n.gsec_meta||{};
 q('#market').innerHTML=[['NIFTY 50',n.level.toLocaleString('en-IN')],['P/E',fmt(n.pe)],['P/B',fmt(n.pb)],['Dividend yield',fmt(n.div_yield)+'%'],['NIFTY date',n.date],['India ~10Y',fmt(n.gsec10)+'%'],['India yield date',gm.asof||'Unknown — excluded'],['India yield status',gm.status||'Undated — excluded'],['India yield instrument',gm.security||gm.source||'Unverified']].map(x=>`<div>${esc(x[0])}</div><div>${esc(x[1])}</div>`).join('');
 q('#earn').innerHTML=[['Index-implied EPS',fmt(en.eps,1)],['Cycle observation date',en.asof||'Unverified'],['EPS growth, 12 months',signed(en.eps_growth_12m)+'%'],['Growth acceleration, 6 months',signed(en.acceleration_6m)+' pp'],['Earnings score',r.earningsEligible?signed(en.score,2):'Excluded']].map(x=>`<div>${esc(x[0])}</div><div>${esc(x[1])}</div>`).join('');
 const score=r.macroEligible?m.score:null,st=stance(score);q('#mscore').textContent=signed(score,2);q('#mstance').textContent=st[0];q('#mcov').textContent=fmt(100*r.coverage,0)+'%';q('#vix').textContent=fmt(m.vix,1);q('#carry').textContent=fmt(m.india_us_10y_spread)+' pp';
 const qualityOk=packetOk&&factors.vix?.status==='live'&&finite(d.confidence);
 q('#confbar').style.width=(qualityOk?clip(d.confidence,0,1)*100:0)+'%';
 q('#conf').textContent=qualityOk?`${fmt(d.confidence*100,0)}/100 data/stress indicator — a heuristic, not a probability of profit or statistical confidence. It does not execute or schedule trades.`:'Data/stress indicator unavailable because current, dated inputs are missing.';
 q('#sources').innerHTML=(d.sources||[]).map(s=>`<p><b>${esc(s.name)}</b><br>${esc(s.role)}${s.url&&/^https:\/\//.test(s.url)?`<br><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">Source</a>`:''}</p>`).join('');
 const old=!packetOk;
 q('#status').textContent=`${old?'Old published file — overlays excluded':'Published data'} · NIFTY ${n.date} · refresh ${new Date(d.generated_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})} IST`;
 q('#status').className='status '+(old?'bad':'warn');
}
let requestNumber=0;
async function loadData(){
 const request=++requestNumber,controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
 q('#status').textContent='Checking latest published data…';
 try{
  // Scheduled GITHUB_TOKEN commits do not trigger a branch-based Pages rebuild.
  // Read the public branch data directly so scheduled refreshes are visible immediately.
  const dataURL='https://raw.githubusercontent.com/anuppaul007/anup-nifty-valuation/main/data/latest.json';
  const response=await fetch(dataURL+'?t='+Date.now(),{cache:'no-store',signal:controller.signal});
  if(!response.ok)throw Error('HTTP '+response.status);
  const d=await response.json();if(request===requestNumber)render(d);
 }catch(error){if(request===requestNumber)clearAllocation('Published data could not be loaded. Allocation is withheld; please try again later.');}
 finally{clearTimeout(timer);}
}
loadData();
