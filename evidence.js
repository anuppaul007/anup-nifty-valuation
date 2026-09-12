(function(root){
'use strict';
function selectRows(rows,filter='all',era='all'){
 return rows.filter(r=>Number.isFinite(r.core_equity)&&Number.isFinite(r.core_debt)&&
  (era!=='current'||r.nifty_asof>='2021-03-31')&&
  (filter==='all'||(filter==='equity'&&r.core_equity>80)||(filter==='debt'&&r.core_debt>80)));
}
const api={selectRows};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
else root.AnupEvidence=api;
})(typeof window!=='undefined'?window:this);
