(() => {
'use strict';
const el=id=>document.getElementById(id);
let history=[];
function paint(){
 const rows=AnupEvidence.selectRows(history,el('historyFilter').value,el('historyEra').value);
 el('historyCount').textContent=`${rows.length} matching months · ${history.length} monthly observations in the published snapshot`;
 const body=el('historyRows');body.replaceChildren();
 for(const r of rows){const tr=document.createElement('tr');for(const value of [r.signal_date,r.nifty_asof,r.core_equity.toFixed(2)+'%',r.core_debt.toFixed(2)+'%',r.gsec_asof,AnupEvidence.yieldAgeDays(r)+' days',AnupEvidence.ratioEra(r.nifty_asof)]){const td=document.createElement('td');td.textContent=value;tr.appendChild(td);}body.appendChild(tr);}
}
async function currentFile(name){
 if(typeof fetchPublished==='function'){const c=new AbortController(),t=setTimeout(()=>c.abort(),12000);try{return await fetchPublished(name,c.signal);}finally{clearTimeout(t);}}
 const response=await fetch('data/'+name,{cache:'no-store'});if(!response.ok)throw Error('Published file unavailable');return response.json();
}
function signed(v,d=2){const n=Number(v);if(!Number.isFinite(n))return '—';return `${n>0?'+':''}${n.toFixed(d)}`;}
function pct(v,d=2){const n=Number(v);return Number.isFinite(n)?`${n.toFixed(d)}%`:'—';}
function cell(row,text,tag='td'){const x=document.createElement(tag);x.textContent=text;row.appendChild(x);return x;}
function table(headers,rows){
 const t=document.createElement('table'),head=document.createElement('thead'),hr=document.createElement('tr');headers.forEach(h=>cell(hr,h,'th'));head.appendChild(hr);t.appendChild(head);
 const body=document.createElement('tbody');for(const values of rows){const tr=document.createElement('tr');values.forEach(v=>cell(tr,v));body.appendChild(tr);}t.appendChild(body);return t;
}
async function loadAuditDisclosure(){
 const host=el('validation-evidence');
 if(!host||typeof host.appendChild!=='function')return;
 const wrap=document.createElement('div');wrap.id='timingInsuranceDisclosure';wrap.className='flag';
 const title=document.createElement('h3');title.textContent='Timing effect and the price of the SMA10 brake';title.style.margin='0 0 8px';wrap.appendChild(title);
 try{
  const b=await currentFile('benchmark_audit.json');
  const lead=document.createElement('p'),strong=document.createElement('strong');strong.textContent=b.observed_tradeoff_sentence;lead.appendChild(strong);wrap.appendChild(lead);
  const order=['ex_post_realised_mean_static','fixed_60_40_policy','expanding_mean_investable'];
  const rows=order.map(k=>{const q=b.comparators[k];return [q.name,q.available_ex_ante?'Yes':'No',pct(q.comparator_mean_equity_pct,2),`${signed(q.dynamic_minus_comparator_cagr_pp,2)} pp/yr`,`${signed(q.dynamic_additional_drawdown_pp,2)} pp`];});
  wrap.appendChild(table(['Comparator','Available at the time?','Avg equity','Dynamic CAGR edge','Additional drawdown'],rows));
  const note=document.createElement('p');note.className='muted';
  const fx=b.comparators.fixed_60_40_policy,ex=b.comparators.expanding_mean_investable;
  note.textContent=`The 53.54% full-sample mean comparator is an ex-post beta-removal diagnostic, not an investable starting policy. Against fixed 60/40 the dynamic rule changed CAGR by ${signed(fx.dynamic_minus_comparator_cagr_pp,2)} pp/yr and drawdown by ${signed(fx.dynamic_additional_drawdown_pp,2)} pp. Against the expanding-mean investable null it changed CAGR by ${signed(ex.dynamic_minus_comparator_cagr_pp,2)} pp/yr, but that comparator averaged only ${pct(ex.comparator_mean_equity_pct,2)} equity, so this is not a pure timing-alpha comparison.`;wrap.appendChild(note);
  const h=b.observed_effect_scale,scale=document.createElement('p');scale.className='muted';scale.textContent=`Observed timing-residual t-stat: ${Number(h.observed_naive_t_stat).toFixed(2)}. Mechanical scaling to |t|=2 is about ${Math.round(h.raw_years_if_iid_effect_persisted).toLocaleString()} years under IID assumptions and about ${Math.round(h.serial_dependence_adjusted_years_if_same_efficiency_persisted).toLocaleString()} years if the observed effective-sample efficiency persisted. These are heuristic illustrations, not forecasts: the prospective ledger is intended to detect a materially larger stable edge if one emerges and otherwise document its absence.`;wrap.appendChild(scale);
  const link=document.createElement('a');link.href='data/benchmark_audit.json';link.textContent='Machine-readable comparator audit';wrap.appendChild(link);
 }catch{
  const p=document.createElement('p');p.className='muted';p.textContent='The investable timing-benchmark audit is temporarily unavailable; no substitute result is inferred.';wrap.appendChild(p);
 }
 try{
  const ins=await currentFile('sma10_insurance_audit.json'),s=ins.same_63_calendar_return_months,l=ins.longest_exact_shared_history;
  const h=document.createElement('h4');h.textContent='SMA10 brake — insurance premium versus protection';wrap.appendChild(h);
  wrap.appendChild(table(['Window','CAGR premium paid','Max daily drawdown avoided','Avg equity reduction'],[
   [`Same ${s.calendar_return_months} calendar return months`,`${signed(s.cagr_premium_paid_pp_per_year,2)} pp/yr`,`${signed(s.max_daily_drawdown_avoided_pp,2)} pp`,`${signed(s.average_equity_reduction_pp,2)} pp`],
   ['Longest exact shared history',`${signed(l.cagr_premium_paid_pp_per_year,2)} pp/yr`,`${signed(l.max_daily_drawdown_avoided_pp,2)} pp`,`${signed(l.average_equity_reduction_pp,2)} pp`]
  ]));
  const p=document.createElement('p');p.className='muted';p.textContent='The SMA10 −20 pp rule is disclosed here as a policy insurance choice, not demonstrated timing alpha. Its historical pre-registered promotion hurdle failed; keeping it live by owner-approved policy override does not erase the premium or convert the rule into validated alpha.';wrap.appendChild(p);
  const link=document.createElement('a');link.href='data/sma10_insurance_audit.json';link.textContent='Machine-readable SMA10 insurance audit';wrap.appendChild(link);
 }catch{
  const p=document.createElement('p');p.className='muted';p.textContent='The SMA10 insurance-price snapshot is awaiting its independent audit publication; the live brake is not treated as validated alpha while that disclosure is unavailable.';wrap.appendChild(p);
 }
 host.appendChild(wrap);
}
async function load(){
 try{const response=await fetch('data/monthly_signal_screen.json',{cache:'no-store'});if(!response.ok)throw Error();const data=await response.json();history=data.records;paint();}catch{el('historyCount').textContent='Historical screen could not be loaded. No historical signals are inferred from current data.';}
 try{const data=await currentFile('evidence_status.json');
  el('evidenceStatus').textContent=`${data.snapshot_count} immutable input snapshots · ${data.decision_count} first-eligible monthly decisions · Archive began ${data.archive_started_at}. Original historical publication vintages remain unverified.`;
  el('frozenModel').href=`https://github.com/anuppaul007/anup-nifty-valuation/blob/main/data/evidence/models/${data.current_model}.json`;el('frozenModel').hidden=false;
  el('snapshotLink').href=`https://github.com/anuppaul007/anup-nifty-valuation/blob/main/data/evidence/snapshots/${data.latest_snapshot_id}.json`;el('snapshotLink').hidden=false;
 }catch{el('evidenceStatus').textContent='Latest archive status could not be loaded. The original committed records remain available through the links above.';}
 try{const data=await currentFile('health.json');const age=(Date.now()-Date.parse(data.checked_at))/3600000;
  const old=!Number.isFinite(age)||age<0||age>8;el('operationalStatus').textContent=old?'Monitoring report is overdue — the watchdog itself may be delayed.':`Operational checks: ${data.status==='healthy'?'passed':'ATTENTION REQUIRED'} · checked ${age.toFixed(1)} hours ago. ${data.checks.filter(c=>!c.ok).map(c=>c.detail).join('; ')}`;el('operationalStatus').className='flag '+(!old&&data.status==='healthy'?'good':'bad');
 }catch{el('operationalStatus').textContent='Operational monitoring status is unavailable. The live packet age is checked separately above.';}
 await loadAuditDisclosure();
}
el('historyFilter').addEventListener('change',paint);el('historyEra').addEventListener('change',paint);
el('downloadHistory').addEventListener('click',()=>{
 const rows=AnupEvidence.selectRows(history,el('historyFilter').value,el('historyEra').value);
 const csv=[['Decision date','Prior NIFTY observation','Core equity percent','Core debt percent','Yield observation','Yield age days','Ratio era','Scope'],...rows.map(r=>[r.signal_date,r.nifty_asof,r.core_equity,r.core_debt,r.gsec_asof,AnupEvidence.yieldAgeDays(r),AnupEvidence.ratioEra(r.nifty_asof),'Legacy V3.6 retrospective core only'])].map(r=>r.join(',')).join('\r\n');
 const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='Anup_Nifty_monthly_signal_screen.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});load();
})();
