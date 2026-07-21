---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S269'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.iva_compensation`, `aeat.domain.modelos`

## Scope

- `src/aeat/application/live/_filed_observation_persistence.py`
## Description

- Reconcile $display as an individual exec record for a W02 production consumer-rewrite row already checked in the plan.
- Preserve the row intent: Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.iva_compensation`, `aeat.domain.modelos`.
- Tie this row to the broad application rewrite batch recorded by `W02.P49.S240` and landed in `d67ccc42a`.
- Record no new implementation work; this document splits already-landed batched evidence into the required one-record-per-step shape.

## Outcome

The checked row now has its own exec record. The matching anchor evidence for $anchor recorded codemod dry-run/apply, comment-preservation repair in `application.diagnostics`, import sorting and formatting, and clean `pytest --collect-only -q src/aeat` for the 25-file batch. After the bulk scaffold pass, plan status reports xec_missing_ids is empty.

## Notes

Evidence-only reconciliation. The codebase has continued to evolve after the original W02 landing, so this record cites the historical landed evidence and does not claim a fresh source edit.
