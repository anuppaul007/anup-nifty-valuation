const test=require('node:test'),assert=require('node:assert/strict');
const {selectRows}=require('../evidence.js');
test('strict thresholds use unrounded values',()=>{
 const rows=[80,80.00001,20,19.99999].map(core_equity=>({core_equity,core_debt:100-core_equity,nifty_asof:'2026-08-31'}));
 assert.deepEqual(selectRows(rows,'equity'),[rows[1]]);assert.deepEqual(selectRows(rows,'debt'),[rows[3]]);
});
test('era filter and invalid inputs',()=>{
 const rows=[{core_equity:90,core_debt:10,nifty_asof:'2020-03-31'},{core_equity:85,core_debt:15,nifty_asof:'2023-09-29'},{core_equity:null,core_debt:90,nifty_asof:'2026-08-31'}];
 assert.deepEqual(selectRows(rows,'equity','current'),[rows[1]]);
});
test('published reconstruction matches the verified workbook',()=>{
 const rows=require('../data/monthly_signal_screen.json').records;
 assert.equal(rows.length,321);assert.equal(selectRows(rows,'equity').length,100);assert.equal(selectRows(rows,'debt').length,59);
 for(const r of rows){assert.ok(r.nifty_asof<r.signal_date);assert.ok(Math.abs(r.core_equity+r.core_debt-100)<1e-8);}
});
test('page loads history, filters debt and exports selected rows',async()=>{
 const vm=require('node:vm'),fs=require('node:fs');
 const nodes=new Map();
 function element(){return {children:[],events:{},value:'',textContent:'',appendChild(x){this.children.push(x)},replaceChildren(){this.children=[]},addEventListener(k,fn){this.events[k]=fn},click(){}};}
 for(const id of ['historyFilter','historyEra','historyRows','historyCount','evidenceStatus','frozenModel','snapshotLink','downloadHistory','operationalStatus'])nodes.set(id,element());
 nodes.get('historyFilter').value='equity';nodes.get('historyEra').value='all';
 let downloaded;
 const context={AnupEvidence:require('../evidence.js'),document:{getElementById:id=>nodes.get(id),createElement:element},fetch:async url=>({ok:true,json:async()=>url.includes('monthly')?require('../data/monthly_signal_screen.json'):{snapshot_count:1,decision_count:1,archive_started_at:'2026-09-12',current_model:'abc',latest_snapshot_id:'def'}}),Blob,URL:{createObjectURL:b=>{downloaded=b;return 'blob:test'},revokeObjectURL(){}},setTimeout:fn=>fn()};
 vm.runInNewContext(fs.readFileSync(require.resolve('../evidence-ui.js'),'utf8'),context);
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(nodes.get('historyRows').children.length,100);
 nodes.get('historyFilter').value='debt';nodes.get('historyFilter').events.change();
 assert.equal(nodes.get('historyRows').children.length,59);
 nodes.get('downloadHistory').events.click();assert.equal((await downloaded.text()).split('\r\n').length,60);
 assert.equal(nodes.get('frozenModel').href,'https://github.com/anuppaul007/anup-nifty-valuation/blob/main/data/evidence/models/abc.json');
});
test('yield age is observation age, not an asserted release lag',()=>{
 assert.equal(require('../evidence.js').yieldAgeDays({signal_date:'2000-01-01',gsec_asof:'1999-11-30'}),32);
});

test('2021 PE transition does not make legacy PB comparable',()=>{
 const rows=['2021-03-31','2023-09-28','2023-09-29'].map(nifty_asof=>({nifty_asof,core_equity:85,core_debt:15}));
 assert.deepEqual(selectRows(rows,'all','current'),[rows[2]]);
});
