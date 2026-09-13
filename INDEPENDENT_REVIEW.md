# Independent review protocol

Status: **not yet independently reviewed**. Prepared by the model developer;
this protocol is a handoff, not a signed validation opinion. No reviewer has been
contacted or appointed by this release.

Review a fixed commit, not a moving branch. Record the commit, dependencies,
input hashes, observation dates and time at which each input became knowable.
Reviewers should have no role in selecting the model or its thresholds and must
be able to publish adverse findings without the developer removing them.

## Required work

1. Recompute the current target in a separately written implementation. Do not
   simply call the supplied engine and treat agreement as independent reproduction.
2. Challenge whether the valuation references identify anything beyond a short
   sample's historical norms. Test constituent/sector composition, definition
   breaks, profitability normalization and redundant earnings exposure.
3. Try malformed, revised, stale, duplicated and missing source observations.
   Inspect release timing, not just an observation's reference month.
4. Reproduce the historical evaluator independently: investable benchmarks,
   execution lag, total returns, drift-aware turnover, serial dependence,
   selection burden and the identity of all attempted variants.
5. Evaluate the crash brake's loss reduction and opportunity cost separately.
   Include intramonth gaps and recovery participation, rather than only month ends.
6. Evaluate fees, taxes and realistic instrument constraints before claiming a
   taxable investor could obtain the backtest outcome. Define every tax assumption.
7. Report every material defect with a reproducible counterexample, severity,
   affected versions, proposed remedy and retest status. List untestable claims.

## Deliverable and acceptance

Publish reviewer identity/conflicts, exact scope, replication files, findings and
limitations. A second AI response is useful challenge but does not by itself
constitute a separate accountable model-risk function.

The developer responds to each finding; the reviewer determines whether its
resolution reproduces. Unresolved material findings remain visible. Independent
review permits an explicit use decision within its tested scope; it cannot
certify guaranteed returns, universal optimality or crash-proof allocation.
