---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:828a1ca8d3b08e74d38e14ad5a88f27e75e4c5f1b5c99b420cb1d103a44c96e2'
step_id: 'S50'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`

## Scope

- `src/aeat/application/modelo/_action_errors.py`
## Description

- Reconcile $display as an individual exec record for a W02 production consumer-rewrite row already checked in the plan.
- Preserve the row intent: Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`.
- Tie this row to the `aeat.application.modelo` production rewrite batch recorded by `W02.P36.S49` and landed in `01ec29a3e`.
- Record no new implementation work; this document splits already-landed batched evidence into the required one-record-per-step shape.

## Outcome

The checked row now has its own exec record. The matching anchor evidence for $anchor recorded codemod dry-run/apply, import sorting and formatting, and clean `pytest --collect-only -q src/aeat` for the 47-file batch. After the bulk scaffold pass, plan status reports xec_missing_ids is empty.

## Notes

Evidence-only reconciliation. The codebase has continued to evolve after the original W02 landing, so this record cites the historical landed evidence and does not claim a fresh source edit.
