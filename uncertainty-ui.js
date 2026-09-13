(() => {
'use strict';
const fmt=(x,d=1)=>typeof x==='number'&&Number.isFinite(x)?x.toFixed(d):'—';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function published(name){
 const urls=[`data/${name}`,`https://api.github.com/repos/anuppaul007/anup-nifty-valuation/contents/data/${name}`,`https://raw.githubusercontent.com/anuppaul007/anup-nifty-valuation/main/data/${name}`];
 let last;
 for(const url of urls){
  try{
   const r=await fetch(url+'?t='+Date.now(),{cache:'no-store',headers:{Accept:'application/vnd.github.raw+json'}});
   if(!r.ok)throw Error('HTTP '+r.status);
   const p=await r.json();
   return p&&p.encoding==='base64'&&typeof p.content==='string'?JSON.parse(atob(p.content.replace(/\s/g,''))):p;
  }catch(e){last=e;}
 }
 throw last||Error('published file unavailable');
}
function makeTable(rows){
 const table=document.createElement('table');
 table.innerHTML='<thead><tr><th>Calibration lens</th><th>Largest allocation sensitivity</th></tr></thead><tbody>'+rows.map(([k,v])=>`<tr><td>${esc(k)}</td><td>${fmt(v.max_abs_change_pp,2)} pp</td></tr>`).join('')+'</tbody>';
 return table;
}
async function loadCalibrationDisclosure(){
 const host=document.getElementById('valuation-range');
 if(!host||document.getElementById('calibrationStabilityDisclosure'))return;
 const box=document.createElement('div');box.id='calibrationStabilityDisclosure';box.className='flag';box.setAttribute('role','status');
 box.textContent='Checking calibration sensitivity…';
 const stress=document.getElementById('portfolioStress');
 if(stress&&stress.parentNode===host)host.insertBefore(box,stress.nextSibling);else host.appendChild(box);
 try{
  const [a,latest]=await Promise.all([published('calibration_stability_audit.json'),published('latest.json')]);
  const same=a?.research_only===true&&a?.model_version===latest?.model_version&&a?.current_packet?.generated_at===latest?.generated_at;
  if(!same){box.className='flag bad';box.textContent='Calibration-sensitivity disclosure is not synchronized with the current live packet, so its range is withheld.';return;}
  const p=a.production_reproduction||{},b=a.leave_six_month_block_out||{},lens=a.one_lens_at_a_time_leave_block_sensitivity||{};
  const rows=Object.entries(lens).sort((x,y)=>(y[1]?.max_abs_change_pp||0)-(x[1]?.max_abs_change_pp||0));
  box.className='flag warn';box.replaceChildren();
  const lead=document.createElement('p');lead.style.margin='0 0 8px';
  lead.innerHTML=`<strong>Calibration sensitivity — do not read ${fmt(p.policy_equity_pct,1)}% as precise.</strong> Re-estimating the four lens centres/scales after leaving out different contiguous six-month blocks of the short 36-month current-definition sample moves today’s policy-equity reading from <strong>${fmt(b.min_policy_equity_pct,1)}% to ${fmt(b.max_policy_equity_pct,1)}%</strong>, a ${fmt(b.range_pp,1)} pp span.`;
  box.appendChild(lead);
  const note=document.createElement('p');note.className='muted';note.textContent='This is an assumption-fragility range, not a confidence interval, intrinsic-value band or alternative live recommendation. V3.13 remains frozen at the published live target; the audit has zero allocation authority.';box.appendChild(note);
  if(rows.length)box.appendChild(makeTable(rows));
  const link=document.createElement('a');link.href='data/calibration_stability_audit.json';link.textContent='Machine-readable calibration-stability audit';box.appendChild(link);
 }catch(e){box.className='flag bad';box.textContent='Calibration-sensitivity audit is unavailable. No uncertainty range is inferred from stale or missing data.';}
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',loadCalibrationDisclosure,{once:true});else loadCalibrationDisclosure();
})();
