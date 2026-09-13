(function(root){
'use strict';
function selectRows(rows,filter='all',era='all'){
 return rows.filter(r=>Number.isFinite(r.core_equity)&&Number.isFinite(r.core_debt)&&
  (era!=='current'||r.nifty_asof>='2023-09-29')&&
  (filter==='all'||(filter==='equity'&&r.core_equity>80)||(filter==='debt'&&r.core_debt>80)));
}
function yieldAgeDays(r){return Math.round((Date.parse(r.signal_date)-Date.parse(r.gsec_asof))/86400000);}
function ratioEra(date){return date<'2021-03-31'?'Legacy PE and PB':date<'2023-09-29'?'Consolidated PE; legacy PB':'Current ratio definitions';}
const api={selectRows,yieldAgeDays,ratioEra};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
else root.AnupEvidence=api;
})(typeof window!=='undefined'?window:this);

// Browser-only disclosure module. It has no access to or authority over the
// model calculation; it only renders the synchronized research audit.
if(typeof document!=='undefined'){
 const s=document.createElement('script');
 s.src='uncertainty-ui.js?v=20260913-1';
 s.defer=true;
 document.head.appendChild(s);
}
