---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:60dabc37b4f5ec9038f816b051dcf53e372ce2af88fd8cad5809ecbbeb2620ce'
step_id: 'S92'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 11 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.calculations`, `aeat.domain.modelos`

## Scope

- `src/aeat/application/modelo/_verification_cross_period.py`
## Description

- Reconcile $display as an individual exec record for a W02 production consumer-rewrite row already checked in the plan.
- Preserve the row intent: Rewire 11 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.calculations`, `aeat.domain.modelos`.
- Tie this row to the `aeat.application.modelo` production rewrite batch recorded by `W02.P36.S49` and landed in `01ec29a3e`.
- Record no new implementation work; this document splits already-landed batched evidence into the required one-record-per-step shape.

## Outcome

The checked row now has its own exec record. The matching anchor evidence for $anchor recorded codemod dry-run/apply, import sorting and formatting, and clean `pytest --collect-only -q src/aeat` for the 47-file batch. After the bulk scaffold pass, plan status reports xec_missing_ids is empty.

## Notes

Evidence-only reconciliation. The codebase has continued to evolve after the original W02 landing, so this record cites the historical landed evidence and does not claim a fresh source edit.
