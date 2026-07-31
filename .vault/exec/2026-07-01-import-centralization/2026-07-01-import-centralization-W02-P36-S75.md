---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:1323419c4a6e0931bad8d67b722c313ca350ed0182a224cc6ae17cb57d244783'
step_id: 'S75'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 14 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`

## Scope

- `src/aeat/application/modelo/_participation_index_rebuild.py`
## Description

- Reconcile $display as an individual exec record for a W02 production consumer-rewrite row already checked in the plan.
- Preserve the row intent: Rewire 14 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`.
- Tie this row to the `aeat.application.modelo` production rewrite batch recorded by `W02.P36.S49` and landed in `01ec29a3e`.
- Record no new implementation work; this document splits already-landed batched evidence into the required one-record-per-step shape.

## Outcome

The checked row now has its own exec record. The matching anchor evidence for $anchor recorded codemod dry-run/apply, import sorting and formatting, and clean `pytest --collect-only -q src/aeat` for the 47-file batch. After the bulk scaffold pass, plan status reports xec_missing_ids is empty.

## Notes

Evidence-only reconciliation. The codebase has continued to evolve after the original W02 landing, so this record cites the historical landed evidence and does not claim a fresh source edit.
