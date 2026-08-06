---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:84d947f6a5edb772971be29a3907f95df048fb62f08467bc173cf69dc87124ea'
step_id: 'S165'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 4 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.buckets`, `aeat.domain.modelos`, `aeat.domain.transactions`

## Scope

- `src/aeat/application/ledger/_actions_split_merge.py`
## Description

- Reconcile $display as an individual exec record for a W02 production consumer-rewrite row already checked in the plan.
- Preserve the row intent: Rewire 4 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.buckets`, `aeat.domain.modelos`, `aeat.domain.transactions`.
- Tie this row to the `aeat.application.ledger` production rewrite batch recorded by `W02.P40.S159` and landed in `3a83394c6`.
- Record no new implementation work; this document splits already-landed batched evidence into the required one-record-per-step shape.

## Outcome

The checked row now has its own exec record. The matching anchor evidence for $anchor recorded codemod dry-run/apply, import sorting and formatting, and clean `pytest --collect-only -q src/aeat` for the 16-file batch. After the bulk scaffold pass, plan status reports xec_missing_ids is empty.

## Notes

Evidence-only reconciliation. The codebase has continued to evolve after the original W02 landing, so this record cites the historical landed evidence and does not claim a fresh source edit.
