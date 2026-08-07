---
tags:
  - '#exec'
  - '#llm-package-split'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:98143f3baa582025e2593b8c8085bd013a35f9942e3f373957e35e9538f76beb'
step_id: 'S79'
related:
  - "[[2026-08-06-llm-package-split-plan]]"
---

# Add a representable recargo slot to the extraction draft, since the printed-total discrepancy advisory now fires with no field for the operator to resolve it into, red if a recargo-bearing document still leaves the operator no place to record it

## Scope

- `src/cadrumo/application/ledger/_evidence_draft.py`

## Description

## Outcome

## Verification

## Notes

This record was reconstructed during a tracker reconciliation, not written by
the agent that executed the Step. The campaign landed roughly fifty Steps across
twenty commits while the plan tracker still read `0/83`, so the records were
recovered from the commit history rather than authored at execution time.

The Step is carried by commit `796914c2e3`, whose message cites it by identifier, and
its artifact was confirmed present at HEAD before the box was ticked. The full
step-to-commit mapping, the steps deliberately left unticked, and the
implementation-versus-plan deviation found along the way are in
`2026-08-07-llm-package-split-plan-tracker-reconciliation-audit`.

What this record does NOT carry is the executing agent's own account of the
work: the reasoning, the alternatives weighed, and the surprises met are in the
commit message and nowhere else. That is the cost of records written after the
fact, and it is why the gate wants them written at execution time.
