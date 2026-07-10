---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S18'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
---




# Close cross-domain task #62 and update the source-jurisdiction ADR consequences with the verified M210 implementation commit SHAs

## Scope

- `.vault/adr/2026-05-27-source-jurisdiction-axis-adr.md`

## Description


- Reconcile the source-jurisdiction ADR with the delivered M210 ledger projection.
- Correct the M210 legal roles: Article 13.1 territorial scope, Article 24 base, and Article 25 rate.
- Record the implementation and locale verification commit and distinguish the M210 closure from the deferred M151 work.

## Outcome

Task #62 is closed only for the M210 source-jurisdiction projection delivered in `8f5f690ed0`. The source ADR now records the persisted classification, source-mode, evidence, and typed-exclusion behavior; it does not claim completion for M151.

## Notes


Historical execution records remain unchanged.
