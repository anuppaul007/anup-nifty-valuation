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
function signed(v,d=2){if(typeof v!=='number'||!Number.isFinite(v))return '—';return `${v>0?'+':''}${v.toFixed(d)}`;}
function pct(v,d=2){return typeof v==='number'&&Number.isFinite(v)?`${v.toFixed(d)}%`:'—';}
function cell(row,text,tag='td'){const x=document.createElement(tag);x.textContent=text;row.appendChild(x);return x;}
function table(headers,rows){
 const t=document.createElement('table'),head=document.createElement('thead'),hr=document.createElement('tr');headers.forEach(h=>cell(hr,h,'th'));head.appendChild(hr);t.appendChild(head);
 const body=document.createElement('tbody');for(const values of rows){const tr=document.createElement('tr');values.forEach(v=>cell(tr,v));body.appendChild(tr);}t.appendChild(body);return t;
}
async function loadAuditDisclosure(){
 const host=el('validation-evidence');
 if(!host||typeof host.appendChild!=='function')return;
 const wrap=document.createElement('div');wrap.id='timingInsuranceDisclosure';wrap.className='flag';
 const title=document.createElement('h3');title.textContent='Timing, crash-insurance and macro-authority evidence';title.style.margin='0 0 8px';wrap.appendChild(title);
 try{
  const b=await currentFile('benchmark_audit.json');
  const lead=document.createElement('p'),strong=document.createElement('strong');strong.textContent=b.observed_tradeoff_sentence;lead.appendChild(strong);wrap.appendChild(lead);
  const liveNull=document.createElement('p'),liveStrong=document.createElement('strong');liveStrong.textContent=b.decision_relevant_60_40_sentence||'Against the pre-declared 60/40 policy, the decision-relevant comparison is unavailable.';liveNull.appendChild(liveStrong);wrap.appendChild(liveNull);
  const order=['expanding_mean_investable','ex_post_realised_mean_static','fixed_60_40_policy'];
  const rows=order.map(k=>{const q=b.comparators[k];return [q.name,q.available_ex_ante?'Yes':'No',pct(q.comparator_mean_equity_pct,2),`${signed(q.dynamic_minus_comparator_cagr_pp,2)} pp/yr`,`${signed(q.dynamic_additional_drawdown_pp,2)} pp`];});
  wrap.appendChild(table(['Comparator','Available at the time?','Avg equity','Dynamic CAGR edge','Additional drawdown'],rows));
  const beta=b.comparator_beta_signature||{},betaNote=document.createElement('p');betaNote.className='muted';
  betaNote.textContent=beta.status?`One finding, three comparator weights: dynamic excess CAGR declines by about ${Math.abs(Number(beta.slope_pp_excess_cagr_per_1pp_comparator_equity)).toFixed(3)} pp/year for each 1 pp increase in comparator equity, with a fitted zero crossing near ${pct(beta.fitted_zero_cross_equity_pct,2)} and R² ${Number(beta.r_squared).toFixed(3)}. The fitted edge at the dynamic strategy's own ${pct(beta.dynamic_mean_equity_pct,2)} mean exposure is ${signed(beta.fitted_excess_cagr_at_dynamic_mean_equity_pp,2)} pp/year. This three-point geometry is descriptive only, but it is the pattern expected when most return differences are equity beta and residual timing content is small.`:'Comparator geometry is awaiting publication.';wrap.appendChild(betaNote);
  const h=b.observed_effect_scale,scale=document.createElement('p');scale.className='muted';scale.textContent=`Observed exposure-matched timing-residual t-stat: ${Number(h.observed_naive_t_stat).toFixed(2)}. Mechanical scaling to |t|=2 is about ${Math.round(h.raw_years_if_iid_effect_persisted).toLocaleString()} years under IID assumptions and about ${Math.round(h.serial_dependence_adjusted_years_if_same_efficiency_persisted).toLocaleString()} years if the observed effective-sample efficiency persisted. These are heuristic illustrations, not forecasts: the prospective ledger is intended to detect a materially larger stable edge if one emerges and otherwise document its absence.`;wrap.appendChild(scale);
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
  const p=document.createElement('p');p.className='muted';p.textContent='The SMA10 −20 pp rule is disclosed as policy insurance, not demonstrated timing alpha. Its pre-registered automatic-promotion hurdle failed; keeping it live does not erase its premium or convert it into validated alpha.';wrap.appendChild(p);
  const link=document.createElement('a');link.href='data/sma10_insurance_audit.json';link.textContent='Machine-readable SMA10 insurance audit';wrap.appendChild(link);
 }catch{
  const p=document.createElement('p');p.className='muted';p.textContent='The SMA10 insurance-price snapshot is awaiting publication; the live brake is not treated as validated alpha while that disclosure is unavailable.';wrap.appendChild(p);
 }
 try{
  const epi=await currentFile('sma10_episode_audit.json');
  const h=document.createElement('h4');h.textContent='Did the brake pay during the largest drawdowns?';wrap.appendChild(h);
  wrap.appendChild(table(['Baseline trough','Baseline drawdown','Brake payout','Brake engaged','12m recovery difference'],epi.top_five_drawdown_episodes.map(x=>[
   x.baseline_trough_date,pct(x.baseline_full_episode_drawdown_pct,2),`${signed(x.brake_drawdown_payout_pp,2)} pp`,x.brake_engaged_date||'—',`${signed(x.recovery_12m?.braked_minus_baseline_return_pp,2)} pp`
  ])));
  const c=epi.covid_feb_sep_2020||{},p=document.createElement('p');p.className='muted';
  p.textContent=`COVID timing settles an important boundary case: the brake switched risk-off on ${c.first_risk_off_transition||'—'}, ${Number(c.days_engaged_before_nifty_trough)||0} days before the ${c.nifty_price_trough_date||'—'} NIFTY trough, and switched back risk-on on ${c.first_risk_on_transition_after||'—'}. In the five largest baseline drawdowns the brake reduced drawdown in ${epi.summary?.episodes_with_positive_drawdown_payout??'—'} of 5 episodes; however, 12-month post-trough recovery return was lower in ${epi.summary?.episodes_with_lower_12m_recovery_return??'—'} of 5, with a median difference of ${signed(epi.summary?.median_12m_recovery_return_difference_pp,2)} pp. The evidence therefore says the policy paid during crashes but systematically surrendered some recovery participation.`;wrap.appendChild(p);
  const link=document.createElement('a');link.href='data/sma10_episode_audit.json';link.textContent='Machine-readable crash-episode audit';wrap.appendChild(link);
 }catch{
  const p=document.createElement('p');p.className='muted';p.textContent='The episode-level SMA10 payout audit is awaiting publication; no claim about crash timing is inferred from the aggregate result alone.';wrap.appendChild(p);
 }
 try{
  const mac=await currentFile('macro_authority_audit.json'),cur=mac.current_snapshot||{},gov=mac.governance_recommendation||{},surf=mac.pipeline_surface||{};
  const h=document.createElement('h4');h.textContent='Macro — context and prospective shadow, not live authority';wrap.appendChild(h);
  const p=document.createElement('p'),strong=document.createElement('strong');strong.textContent=`Live macro authority: ${Number(cur.live_macro_budget_pp||0).toFixed(0)} pp. ${Number(cur.shadow_macro_budget_pp||0).toFixed(0)} pp shadow challenger retained when context is fully verified.`;p.appendChild(strong);wrap.appendChild(p);
  wrap.appendChild(table(['Item','Published status'],[
   ['Current macro score',signed(cur.macro_score,3)],
   ['Current live allocation contribution',`${signed(cur.live_macro_adjustment_pp,2)} pp`],
   ['Current shadow contribution',`${signed(cur.shadow_macro_adjustment_pp,2)} pp`],
   ['Pipeline surface',`${surf.top_level_blocks??'—'} blocks · ${surf.scored_factor_nodes??'—'} scored nodes · ${surf.raw_scored_indicators??'—'} raw scored indicators`],
   ['Historical macro-on vs macro-off price',mac.historical_economic_pricing?.status||'unavailable'],
   ['Wrong-but-plausible monthly error probability',mac.operational_risk?.probability_status||'not identifiable']
  ]));
  const note=document.createElement('p');note.className='muted';note.textContent=`The project does not manufacture a historical macro P&L from revised/current-vintage data and does not estimate a silent semantic-error probability from anecdotal incidents. Governance decision: ${gov.decision==='live_budget_zero_context_only_until_priced'?'live macro budget stays at zero until decision value is demonstrated':'see machine-readable audit'}. A future promotion requires a predeclared prospective or certified release-vintage macro-on versus macro-off comparison; any tested alternative macro budgets join their comparable selection family.`;wrap.appendChild(note);
  const link=document.createElement('a');link.href='data/macro_authority_audit.json';link.textContent='Machine-readable macro-authority audit';wrap.appendChild(link);
 }catch{
  const p=document.createElement('p');p.className='muted';p.textContent='The macro-authority audit is temporarily unavailable. V3.12 keeps macro at zero live authority; missing context does not alter the live allocation.';wrap.appendChild(p);
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
