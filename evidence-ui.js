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
}
el('historyFilter').addEventListener('change',paint);el('historyEra').addEventListener('change',paint);
el('downloadHistory').addEventListener('click',()=>{
 const rows=AnupEvidence.selectRows(history,el('historyFilter').value,el('historyEra').value);
 const csv=[['Decision date','Prior NIFTY observation','Core equity percent','Core debt percent','Yield observation','Yield age days','Ratio era','Scope'],...rows.map(r=>[r.signal_date,r.nifty_asof,r.core_equity,r.core_debt,r.gsec_asof,AnupEvidence.yieldAgeDays(r),AnupEvidence.ratioEra(r.nifty_asof),'Legacy V3.6 retrospective core only'])].map(r=>r.join(',')).join('\r\n');
 const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='Anup_Nifty_monthly_signal_screen.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});load();
})();
