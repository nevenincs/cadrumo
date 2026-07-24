---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S19'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

# Prove the composed write is one unit of work with real adapters, gated on a recorder asserting zero commits between the two catalogue writes, an anti-tautology counterpart asserting the pre-fix split shape does commit between them, and a mid-batch revision conflict leaving neither catalogue linked

## Scope

- `src/cadrumo/application/invoices/tests/test_linking_atomicity.py`

## Description

- Add a write-unit recorder that attaches to the live engine the repositories already use, listening on statement execution and on the DBAPI commit event, and reports how many commits fall between the first and last secure-object write.
- Assert the link performs its two catalogue writes with zero commits between them, then reload both catalogues and confirm the consistency checker reports nothing.
- Add the anti-tautology counterpart: persist the same linked catalogues through two independent saves, the shape this writer replaced, and assert the recorder does observe a commit between them.
- Force a real mid-batch failure using the production compare-and-swap revision guard, and assert neither catalogue is linked afterwards.
- Add a strict roundtrip over both catalogues with non-default optional fields populated, plus a proof that a half-written link on disk surfaces as inequality and is named by the detector.

## Outcome

Five real-adapter tests: real ephemeral master key, real SQLite secure-object store, real serializers, no mocks, stubs, patches, or skips. The fault injected in the rollback test is the same optimistic-concurrency conflict production raises, not a substituted component.

The sensitivity of the primary assertion was verified two ways. The split-shape counterpart proves the recorder can report a non-zero count, so a zero is meaningful rather than vacuous. Independently, the production writer was temporarily reverted to the two-save shape and the primary test failed with three commits observed between the writes, then the fix was restored and the module returned to green.

## Notes

A failure genuinely between the two writes is not reachable through the public writer any more, because after the fix there is no between: the commit-count observation is what discriminates the one-unit shape from the two-unit shape, and the revision-conflict test is what proves a failure inside that one unit rolls both catalogues back. Both were needed; neither alone closes the claim.

The recorder counts only commits falling between the first and last write, because reads open and commit their own sessions on either side of the write window.
