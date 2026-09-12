(function(root){
'use strict';
function packetState(packet,now=new Date()){
 if(packet?.schema_version!==4)return{kind:'upgrade',ok:false,text:'Upgrade needed — unsupported data schema. Allocation withheld.'};
 const age=(now.getTime()-Date.parse(packet.generated_at))/3600000;
 if(!Number.isFinite(age)||age<0)return{kind:'invalid',ok:false,text:'Invalid publication time — allocation withheld.'};
 return{kind:age>72?'stale':'current',ok:age<=72,ageHours:age,text:`Published packet age: ${age.toFixed(1)} hours · ${age>72?'STALE — allocation withheld':'within the 72-hour limit; individual input checks also apply'}`};
}
const api={packetState};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.AnupHealth=api;
})(typeof window!=='undefined'?window:this);
