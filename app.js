'use strict';
const {C,calculate,band,clip,finite,fresh}=AnupModel;
const q=s=>document.querySelector(s);
const fmt=(x,d=2)=>finite(x)?x.toFixed(d):'—';
const signed=(x,d=1)=>finite(x)?(x>=0?'+':'')+x.toFixed(d):'—';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[c]));
const stance=x=>!finite(x)?['not scored','warn']:x>.15?['supportive','good']:x<-.15?['headwind','bad']:['near neutral','warn'];
const versionPill=q('.pill');if(versionPill)versionPill.textContent='Web V3.11 · Crash-aware';
if(typeof document.querySelectorAll==='function'){
 for(const n of document.querySelectorAll('.kv div'))if(n.textContent.trim()==='Extreme-valuation damping')n.textContent='Overlay authority after valuation gate';
 for(const n of document.querySelectorAll('p.muted'))if(n.textContent.includes('retained rule gives macro zero influence at extreme valuation endpoints'))n.textContent='V3.11 keeps full macro/earnings overlay authority whenever valuation is below reference and adds a separate 20 pp SMA10 risk-off brake. These are bounded policy controls, not a guarantee against market gaps, crashes or model error.';
}
function clearMultiAsset(message='Multi-asset research data are unavailable.'){
 for(const id of ['maEq','maDebt','maGold','maSilver','maBtc']){const n=q('#'+id);if(n)n.textContent='—';}
 for(const id of ['maGoldScore','maSilverScore','maBtcScore']){const n=q('#'+id);if(n)n.textContent='score —';}
 if(q('#maDrivers'))q('#maDrivers').innerHTML='';
 if(q('#maStatus'))q('#maStatus').textContent=message;
 if(q('#maNote')){q('#maNote').textContent='The NIFTY equity/debt model remains available independently; no missing multi-asset input is neutral-filled.';q('#maNote').className='flag bad';}
}
function renderMultiAsset(ma,sourceGeneratedAt){
 const sameSnapshot=typeof sourceGeneratedAt==='string'&&ma?.source_latest_generated_at===sourceGeneratedAt&&ma?.core_signal_before_metals?.model_version===AnupModel.VERSION;
 if(!ma||ma.status!=='live'||!fresh(ma.generated_at,3)||!ma.core_allocation||!sameSnapshot){
  const mismatch=ma&&ma.status==='live'&&!sameSnapshot;
  clearMultiAsset(ma?.error||(mismatch?'Multi-asset packet does not match the current NIFTY snapshot; allocation is withheld until the synchronized refresh completes.':'Multi-asset research data are unavailable or stale.'));
  return;
 }
 const a=ma.core_allocation,g=ma.gold||{},s=ma.silver||{},b=ma.btc||{};
 if(![a.equity_pct,a.debt_pct,a.gold_pct,a.silver_pct].every(finite)){clearMultiAsset('Multi-asset core allocation failed validation.');return;}
 q('#maEq').textContent=fmt(a.equity_pct,1)+'%';q('#maDebt').textContent=fmt(a.debt_pct,1)+'%';q('#maGold').textContent=fmt(a.gold_pct,1)+'%';q('#maSilver').textContent=fmt(a.silver_pct,1)+'%';q('#maBtc').textContent=finite(b.tactical_signal_pct)?fmt(b.tactical_signal_pct,1)+'%':'—';
 q('#maGoldScore').textContent='score '+signed(g.score,2);q('#maSilverScore').textContent='score '+signed(s.score,2);q('#maBtcScore').textContent=finite(b.score)?'score '+signed(b.score,2)+' · outside core':'outside core 100%';
 q('#maStatus').innerHTML=`<strong>Core allocation = 100%:</strong> NIFTY ${fmt(a.equity_pct,1)}% · Debt ${fmt(a.debt_pct,1)}% · Gold ${fmt(a.gold_pct,1)}% · Silver ${fmt(a.silver_pct,1)}%. BTC is a separate tactical signal.`;
 const gp=g.market||{},sp=s.market||{},bp=b.market||{},gs=s.drivers?.gold_silver_ratio||{};
 const rows=[
  ['Gold',`$${fmt(gp.price,1)}/oz · 12m ${signed(gp.momentum_12m_pct,1)}%`,signed(g.score,2),`core range ${fmt(g.range_pct?.[0],0)}–${fmt(g.range_pct?.[1],0)}%`],
  ['Silver',`$${fmt(sp.price,2)}/oz · Gold/Silver ${fmt(gs.value,1)}`,signed(s.score,2),`core range ${fmt(s.range_pct?.[0],0)}–${fmt(s.range_pct?.[1],0)}%`],
  ['Bitcoin',`$${finite(bp.price)?Math.round(bp.price).toLocaleString('en-US'):'—'} · vs 200d ${signed(bp.vs_ma200_pct,1)}%`,signed(b.score,2),`tactical step ${fmt(b.tactical_signal_pct,1)}% · excluded from core`]
 ];
 q('#maDrivers').innerHTML=rows.map(r=>`<tr><td>${esc(r[0])}</td><td>${esc(r[1])}</td><td>${esc(r[2])}</td><td>${esc(r[3])}</td></tr>`).join('');
 q('#maNote').className='flag warn';q('#maNote').textContent='Research-v1 only: Gold/Silver/BTC weights are transparent assumptions, not optimized or yet validated as one historical portfolio. Gold and Silver are carved proportionally from the existing equity/debt signal; BTC remains a separate tactical sleeve.';
}
function clearAllocation(message){
 for(const id of ['eq','debt','pct','erp','core','eadj','madj','damp','final'])q('#'+id).textContent='—';
 q('#eqbar').style.width='0%';q('#barEq').textContent='Allocation withheld';q('#barDebt').textContent='';
 for(const id of ['lens','macroBlocks','macroDiag','market','earn','sources'])q('#'+id).innerHTML='';
 for(const id of ['mscore','mstance','mcov','vix','carry','conf'])q('#'+id).textContent='—';
 for(const id of ['robustRange','stressCases','returnCases'])q('#'+id).innerHTML='';
 q('#confbar').style.width='0%';q('#pending').textContent='No current data have been verified.';
 q('#verdict').textContent=message;q('#status').textContent=message;q('#status').className='status bad';
}
let lastPublishedPacket=null;
function paintPacketAge(d){
 const state=AnupHealth.packetState(d);q('#packetAge').textContent=state.text;q('#packetAge').className='flag '+(state.ok?'good':'bad');return state;
}
function render(d){
 lastPublishedPacket=d;paintPacketAge(d);
 if(d?.schema_version!==4){clearAllocation('Upgrade needed — this data schema is unsupported. Reload the page after the current publisher finishes; no old-schema allocation is inferred.');return;}
 const r=calculate(d),n=d.nifty||{},m=d.macro||{},en=d.earnings||{},tr=d.trend||{},vd=d.valuation_diagnostics||{};
 if(!r.valid){clearAllocation(r.reason);return;}
 const robustness=AnupRobustness.assess(d);
 q('#robustRange').textContent=robustness?`Assumption range: ${robustness.min.toFixed(0)}–${robustness.max.toFixed(0)}% equity across 24 curve settings. This is a sensitivity range, not a confidence interval. Current downside macro authority: up to ${robustness.macroAuthority.toFixed(1)} pp. SMA10 crash guard: ${r.trendRiskOff?'RISK-OFF, −20 pp':'risk-on, 0 pp'}.`:'Scenario calculations require eligible current inputs.';
 q('#stressCases').innerHTML=robustness?robustness.stress.map(([label,v])=>`<tr><td>${esc(label)}</td><td>${v.toFixed(1)}%</td><td>${(100-v).toFixed(1)}%</td></tr>`).join(''):'';
 q('#returnCases').innerHTML=robustness?robustness.scenarios.map(x=>`<tr><td>${x.growth}%</td><td>${x.exitPE}×</td><td>${signed(x.annual,1)}%</td><td>${signed(x.excess,1)} pp</td></tr>`).join(''):'';
 const eq=r.allocationReady?Math.round(r.final):null,db=r.allocationReady?100-eq:null;
 q('#eq').textContent=r.allocationReady?eq+'%':'—';q('#debt').textContent=r.allocationReady?db+'%':'—';q('#pct').textContent=signed(r.z,2);q('#erp').textContent=Math.round(r.fundamentalCoverage*100)+'%';
 q('#eqbar').style.width=(eq||0)+'%';q('#barEq').textContent=r.allocationReady?'Equity '+eq+'%':'Complete-data gate active';q('#barDebt').textContent=r.allocationReady?'Debt '+db+'%':'';
 const dq=vd.lens_disagreement||{};
 const qualityNotes=[dq.flagged?`Valuation lenses disagree by ${fmt(dq.spread_pp,1)} percentile points; review signal, not proof of a break.`:null,n.gsec_meta?.last_transition?`India yield proxy changed on ${n.gsec_meta.last_transition.asof}; check comparability.`:null,m.relative_em?.quarantine?.length?`${m.relative_em.quarantine.length} EM records quarantined and excluded from calibration.`:null].filter(Boolean);
 if(q('#qualityNotes'))q('#qualityNotes').textContent=qualityNotes.join(' ');
 const rankText=['live','limited_history'].includes(vd.status)&&finite(vd.composite_cheapness)?` Independent current-methodology sanity check: ${vd.composite_cheapness.toFixed(1)}/100 cheapness across ${vd.months} completed months (${vd.label}). It is diagnostic only and does not alter the allocation.`:'';
 const trendText=r.trendEligible?` Trend crash guard is ${r.trendRiskOff?'RISK-OFF and subtracts 20 pp':'risk-on and makes no adjustment'}.`:'';
 q('#verdict').textContent=r.allocationReady?`Valuation is ${band(r.z)} against the model’s fixed references. With all defined inputs eligible, V3.11 gives ${r.final.toFixed(1)}% equity / ${(100-r.final).toFixed(1)}% debt.${trendText}${rankText} This is a transparent risk-control policy, not a guarantee against crashes or a claim of proven market-timing alpha.`:`No equity/debt target is published because ${r.holdReason||'the complete-data gate is not satisfied'}. Fundamental valuation is still shown, but incomplete macro, earnings, bond or trend evidence is never converted into a precise allocation.${rankText}`;
 q('#lens').innerHTML=r.L.map(x=>`<tr><td>${esc(x.label)}</td><td>${fmt(x.now)}</td><td>${fmt(x.reference)}</td><td>${signed(x.z,2)}</td><td>${x.weight.toFixed(1)}%</td></tr>`).join('');
 q('#core').textContent=fmt(r.core,1)+'%';q('#eadj').textContent=r.earningsComplete?signed(r.ea,2)+' pp':'Withheld';q('#madj').textContent=r.macroEligible?signed(r.ma,2)+' pp':'Withheld';q('#damp').textContent=fmt(100*r.damp,0)+'%';q('#final').textContent=r.allocationReady?fmt(r.final,1)+'%':'Withheld';
 q('#overlayNote').textContent=r.allocationReady?`Macro and earnings adjustments each have a ±6 pp limit and currently use ${(100*r.damp).toFixed(1)}% authority. Below-reference valuation keeps full overlay authority instead of damping stress away. SMA10 trend adjustment = ${signed(r.ta,0)} pp (${r.trendRiskOff?'risk-off':'risk-on'}). Macro coverage is 100%; no missing factor is neutral-filled.`:`Complete-data rule: final allocation requires 100% verified macro coverage plus current earnings, India bond and SMA10 trend data. Current verified macro coverage is ${(100*r.coverage).toFixed(1)}%.`;
 const names={global_liquidity:'Global financial conditions',india_external_carry:'India external / carry',india_domestic:'India domestic regime',china_industrial:'China / global industrial cycle'},details=m.block_weight_detail||{},base=C.macroRequiredWeight||1;
 const blockRows=Object.entries(names).filter(([k])=>finite(m.blocks?.[k])&&(details[k]?.internal_coverage||0)>=.999).map(([k,label])=>{const v=m.blocks[k],a=details[k]||{},st=stance(v);return `<tr><td>${label}</td><td class="${st[1]}">${signed(v,2)}</td><td>${fmt(100*(a.strategic_weight||0)/base,1)}%</td><td>100%</td><td>${fmt(100*(a.effective_weight||0)/base,1)}%</td><td>${st[0]}</td></tr>`;});
 q('#macroBlocks').innerHTML=blockRows.length?blockRows.join(''):'<tr><td colspan="6" class="left">No macro block is published until its internal data are fully verified.</td></tr>';
 const ch=m.china_pmi||{},dom=m.domestic||{},df=dom.factors||{},factors=m.factors||{},packetOk=d.schema_version===4&&fresh(d.generated_at,3);
 const defs=[['US 10Y real yield','us_real_10y','%'],['US nominal 10Y','us_10y','%'],['India − US 10Y spread','india_us_10y_spread',' pp'],['Broad USD, ~3 months','usd_3m_pct','%'],['Brent futures, 63 observations','brent_3m_pct','%'],['Fed assets, 26 observations','fed_assets_6m_pct','%'],['VIX','vix',''],['India broad REER','india_reer_bis',''],['USD/INR, ~3 months','usd_inr_3m_pct','%']];
 const rows=defs.flatMap(([label,key,unit])=>{const f=factors[key]||{};return f.status==='live'&&finite(m[key])?[[label,fmt(m[key])+unit,f.asof||'','verified']]:[];});
 const domesticRows=[['India CPI inflation, YoY','india_cpi_yoy','%'],['India IIP growth, YoY','india_iip_yoy','%'],['RBI policy repo rate','india_repo_rate','%']];
 for(const [label,key,unit] of domesticRows){const f=df[key]||{};if(f.status==='live'&&finite(f.value))rows.push([label,fmt(f.value)+unit,f.asof||'','verified']);}
 if(ch.status==='live'&&finite(ch.pmi))rows.push(['China manufacturing PMI',fmt(ch.pmi,1),ch.asof||'','verified']);
 if(ch.status==='live'&&finite(ch.new_orders))rows.push(['China new orders',fmt(ch.new_orders,1),ch.asof||'','verified']);
 q('#macroDiag').innerHTML=rows.length?rows.map(row=>`<tr>${row.map(v=>`<td>${esc(v)}</td>`).join('')}</tr>`).join(''):'<tr><td colspan="4" class="left">Verified macro observations are temporarily unavailable; no target is published.</td></tr>';
 const requiredFactorNames={us_real_10y:'US real yield',usd_3m_pct:'broad USD',fed_assets_6m_pct:'Fed assets',vix:'VIX',brent_3m_pct:'Brent',india_us_10y_spread:'India-US carry',india_reer_bis:'India REER',usd_inr_3m_pct:'USD/INR'};
 const issues=Object.entries(requiredFactorNames).filter(([k])=>factors[k]?.status!=='live').map(([,v])=>v);if(ch.status!=='live')issues.push('China PMI');if(dom.status!=='live')issues.push('India domestic regime');if(!r.trendEligible)issues.push('SMA10 trend guard');
 q('#pending').className='flag '+(r.allocationReady?'good':'bad');
 q('#pending').textContent=r.allocationReady?'Defined-input coverage is complete, including the live trend guard. This does not mean all economic risks are measured, or that the allocation has been statistically proven.':`Allocation withheld. ${issues.length?`Required inputs not yet eligible: ${issues.join(', ')}. `:''}No missing, stale, cached or pending-history value is displayed as a scored input.`;
 const gm=n.gsec_meta||{};const marketRows=[['NIFTY 50',n.level.toLocaleString('en-IN')],['P/E',fmt(n.pe)],['P/B',fmt(n.pb)],['Dividend yield',fmt(n.div_yield)+'%'],['NIFTY date',n.date],['India ~10Y',fmt(n.gsec10)+'%'],['India yield date',gm.asof||'Not verified'],['India yield instrument',gm.security||gm.source||'Not verified']];
 if(r.trendEligible){marketRows.push(['SMA10 crash guard',r.trendRiskOff?'RISK-OFF · −20 pp':'Risk-on · 0 pp']);marketRows.push(['Completed-month NIFTY close',fmt(tr.completed_month_close,1)]);marketRows.push(['10-month average',fmt(tr.sma10,1)]);marketRows.push(['Trend observation date',tr.asof||'Not verified']);}
 if(['live','limited_history'].includes(vd.status)&&finite(vd.composite_cheapness)){marketRows.push(['Valuation-era cheapness',fmt(vd.composite_cheapness,1)+'/100']);marketRows.push(['Comparable completed months',String(vd.months)]);}
 q('#market').innerHTML=marketRows.map(x=>`<div>${esc(x[0])}</div><div>${esc(x[1])}</div>`).join('');
 q('#earn').innerHTML=[['Index-implied EPS',fmt(en.eps,1)],['Cycle observation date',en.asof||'Not verified'],['EPS growth, 12 months',signed(en.eps_growth_12m)+'%'],['Growth acceleration, 6 months',signed(en.acceleration_6m)+' pp'],['Earnings score',r.earningsComplete?signed(en.score,2):'Withheld']].map(x=>`<div>${esc(x[0])}</div><div>${esc(x[1])}</div>`).join('');
 const score=r.macroEligible?m.score:null,st=stance(score);q('#mscore').textContent=r.macroEligible?signed(score,2):'Withheld';q('#mstance').textContent=r.macroEligible?st[0]:'complete data required';q('#mcov').textContent=fmt(100*r.coverage,0)+'%';q('#vix').textContent=factors.vix?.status==='live'?fmt(m.vix,1):'—';q('#carry').textContent=factors.india_us_10y_spread?.status==='live'?fmt(m.india_us_10y_spread)+' pp':'—';
 const stress=finite(m.vix)?clip(1-Math.max(0,m.vix-18)/40,.35,1):null,quality=packetOk&&finite(stress)?stress*(.65+.35*r.coverage):null;q('#confbar').style.width=(finite(quality)?100*quality:0)+'%';q('#conf').textContent=finite(quality)?`${fmt(quality*100,0)}/100 data/stress indicator — heuristic, not probability of profit.`:'Data/stress indicator withheld until current dated inputs are available.';
 const sourceList=(d.sources||[]).filter(s=>!/^STOXX/i.test(String(s.name||'')));q('#sources').innerHTML=sourceList.map(s=>`<p><b>${esc(s.name)}</b><br>${esc(s.role)}${s.url&&/^https:\/\//.test(s.url)?`<br><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">Source</a>`:''}</p>`).join('');
 const old=!packetOk;q('#status').textContent=`${old?'Old published file — target withheld':'Published data'} · ${AnupModel.VERSION} · NIFTY ${n.date} · refresh ${new Date(d.generated_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})} IST`;q('#status').className='status '+(old?'bad':r.allocationReady?'good':'warn');
}
async function fetchPublished(name,signal){
 const urls=[`https://api.github.com/repos/anuppaul007/anup-nifty-valuation/contents/data/${name}`,`https://raw.githubusercontent.com/anuppaul007/anup-nifty-valuation/main/data/${name}`];let lastError;
 for(const url of urls){
  try{
   const response=await fetch(url+'?t='+Date.now(),{cache:'no-store',signal,headers:{Accept:'application/vnd.github.raw+json'}});if(!response.ok)throw Error('HTTP '+response.status);
   const payload=await response.json();const d=payload.encoding==='base64'&&typeof payload.content==='string'?JSON.parse(atob(payload.content)):payload;if(!d)throw Error('Unexpected published data format');return d;
  }catch(error){lastError=error;}
 }
 throw lastError||Error('Data unavailable');
}
let requestNumber=0;
async function loadData(){
 const request=++requestNumber,controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);q('#status').textContent='Checking latest published data…';clearMultiAsset('Checking latest multi-asset research data…');
 try{
  const d=await fetchPublished('latest.json',controller.signal);if(request!==requestNumber)return;render(d);
  if(d?.schema_version!==4){clearMultiAsset('Upgrade needed — unsupported NIFTY source schema.');return;}
  try{const ma=await fetchPublished('multiasset.json',controller.signal);if(request===requestNumber)renderMultiAsset(ma,d.generated_at);}catch(error){if(request===requestNumber)clearMultiAsset('Multi-asset research data could not be loaded; the NIFTY model remains unaffected.');}
 }catch(error){if(request===requestNumber){lastPublishedPacket=null;q('#packetAge').textContent='Publication unavailable — current packet age cannot be verified.';q('#packetAge').className='flag bad';clearAllocation('Published data could not be loaded. Allocation is withheld; please try again later.');clearMultiAsset();}}
 finally{clearTimeout(timer);}
}
setInterval(()=>{if(lastPublishedPacket){const s=paintPacketAge(lastPublishedPacket);if(!s.ok){clearAllocation(s.text);clearMultiAsset('Source packet is stale or unsupported.');}}},60000);
loadData();