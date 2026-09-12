(() => {
'use strict';
const el=id=>document.getElementById(id);
let history=[];
function paint(){
 const rows=AnupEvidence.selectRows(history,el('historyFilter').value,el('historyEra').value);
 el('historyCount').textContent=`${rows.length} matching months · ${history.length} monthly observations in the published snapshot`;
 const body=el('historyRows');body.replaceChildren();
 for(const r of rows){const tr=document.createElement('tr');for(const value of [r.signal_date,r.nifty_asof,r.core_equity.toFixed(2)+'%',r.core_debt.toFixed(2)+'%',r.gsec_asof,r.nifty_asof<'2021-03-31'?'Earlier methodology':'Current methodology']){const td=document.createElement('td');td.textContent=value;tr.appendChild(td);}body.appendChild(tr);}
}
async function load(){
 try{const response=await fetch('data/monthly_signal_screen.json',{cache:'no-store'});if(!response.ok)throw Error();const data=await response.json();history=data.records;paint();}catch{el('historyCount').textContent='Historical screen could not be loaded. No historical signals are inferred from current data.';}
 try{const response=await fetch('data/evidence_status.json',{cache:'no-store'});if(!response.ok)throw Error();const data=await response.json();
  el('evidenceStatus').textContent=`${data.snapshot_count} immutable input snapshots · ${data.decision_count} first-eligible monthly decisions · Archive began ${data.archive_started_at}. Original historical publication vintages remain unverified.`;
  el('frozenModel').href=`data/evidence/models/${data.current_model}.json`;el('frozenModel').hidden=false;
  el('snapshotLink').href=`data/evidence/snapshots/${data.latest_snapshot_id}.json`;el('snapshotLink').hidden=false;
 }catch{el('evidenceStatus').textContent='The new evidence archive has not yet published its first status file. Historical full-model validation is not established.';}
}
el('historyFilter').addEventListener('change',paint);el('historyEra').addEventListener('change',paint);
el('downloadHistory').addEventListener('click',()=>{
 const rows=AnupEvidence.selectRows(history,el('historyFilter').value,el('historyEra').value);
 const csv=[['Decision date','Prior NIFTY observation','Core equity percent','Core debt percent','Yield observation','Scope'],...rows.map(r=>[r.signal_date,r.nifty_asof,r.core_equity,r.core_debt,r.gsec_asof,'Retrospective valuation core only'])].map(r=>r.join(',')).join('\r\n');
 const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='Anup_Nifty_monthly_signal_screen.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});load();
})();
