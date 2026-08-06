---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:61abb7259d7f95ce2adc619803f784a3aa37a9f946a6b075cc9d24eb186b0558'
step_id: 'S15'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
---

# add the anti-tautology test proving the Beckham IRPF base sums only the ES row, the DE row is emitted as a segregated issue with its jurisdiction preserved, and a gate-bypass mutant inflates the IRPF base by the DE row

## Scope

- `src/aeat/application/aggregation`

## Description

- Reconcile the real M151 aggregation test coverage to this historical Step.
- Verify the ES-versus-foreign source-scope witness and the preserved transaction identifier and jurisdiction on the segregation issue.

## Outcome

Completed by commit `24c43acfe8` under the dedicated Modelo 151 source-scope plan. The real-engine test mutates otherwise equivalent ES and FR rows: only ES contributes to the base, while the FR row produces a typed issue carrying its identifier and jurisdiction. The registry-binding test independently includes a DE foreign-source row, so the plan's non-ES witness is covered without coupling correctness to a single country example.

## Notes

No new production code was authored in this reconciliation Step.
