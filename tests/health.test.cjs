const test=require('node:test'),assert=require('node:assert/strict');
const {packetState}=require('../health.js');
test('old schema has an explicit upgrade state',()=>assert.equal(packetState({schema_version:3}).kind,'upgrade'));
test('stale threshold matches the live 72 hour gate',()=>{
 const now=new Date('2026-09-12T00:00:00Z');assert.equal(packetState({schema_version:4,generated_at:'2026-09-09T00:00:00Z'},now).ok,true);
 assert.equal(packetState({schema_version:4,generated_at:'2026-09-08T23:59:59Z'},now).kind,'stale');
 assert.equal(packetState({schema_version:4,generated_at:'2026-09-13T00:00:00Z'},now).kind,'invalid');
});
test('old-schema page clears targets and displays upgrade instructions',()=>{
 const fs=require('node:fs'),vm=require('node:vm'),nodes=new Map();
 const context={AnupModel:{C:{}},AnupHealth:require('../health.js'),document:{querySelector:id=>{if(!nodes.has(id))nodes.set(id,{style:{}});return nodes.get(id)}},setInterval(){},console};
 const source=fs.readFileSync(require.resolve('../app.js'),'utf8').replace(/loadData\(\);\s*$/,'');
 vm.runInNewContext(source,context);vm.runInNewContext('render({schema_version:3})',context);
 assert.match(nodes.get('#verdict').textContent,/Upgrade needed/);assert.equal(nodes.get('#eq').textContent,'—');
});
