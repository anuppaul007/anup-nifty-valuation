'use strict';
const assert=require('assert');
const Guard=require('../macro_guard_candidate.js');

// Cheap endpoint: macro authority must NOT disappear.
assert.strictEqual(Guard.macroDamp(-2.5,0),1);
assert.strictEqual(Guard.macroDamp(-1.0,0.6),1);

// Expensive side keeps the existing damping rule.
assert.strictEqual(Guard.macroDamp(2.5,0),0);
assert.strictEqual(Guard.macroDamp(1.0,0.6),0.6);

const cheapBase={valid:true,allocationReady:true,z:-2.5,damp:0,core:100,ea:0,final:100};
const stressed=Guard.applyToBaseResult(cheapBase,-1);
assert.strictEqual(stressed.candidateMacroDamp,1);
assert.strictEqual(stressed.candidateMacroAdjustment,-6);
assert.strictEqual(stressed.candidateFinal,94);
assert.strictEqual(stressed.candidateDebt,6);

// Positive macro cannot push above 100%.
const supportive=Guard.applyToBaseResult(cheapBase,1);
assert.strictEqual(supportive.candidateFinal,100);

// At the expensive endpoint the candidate does not let bullish macro override
// an extreme valuation signal through the old additive overlay.
const expensiveBase={valid:true,allocationReady:true,z:2.5,damp:0,core:0,ea:0,final:0};
const expensive=Guard.applyToBaseResult(expensiveBase,1);
assert.strictEqual(expensive.candidateMacroAdjustment,0);
assert.strictEqual(expensive.candidateFinal,0);

console.log('macro_guard_candidate tests passed');
