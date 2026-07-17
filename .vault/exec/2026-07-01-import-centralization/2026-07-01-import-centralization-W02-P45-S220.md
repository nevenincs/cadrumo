---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S220'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 4 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.aeat.auth`, `aeat.application.user_profile`, `aeat.application.workflow`

## Scope

- `src/aeat/application/auth/_operator_probes.py`
## Description

- Reconcile $display as an individual exec record for a W02 production consumer-rewrite row already checked in the plan.
- Preserve the row intent: Rewire 4 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.aeat.auth`, `aeat.application.user_profile`, `aeat.application.workflow`.
- Tie this row to the auth/filing/overview/wizard/review/workflow rewrite batch recorded by `W02.P45.S217` and landed in `3c1748da7`, with follow-on shared-leaf cleanup for the review/workflow cycle recorded by the existing specific records in this phase family.
- Record no new implementation work; this document splits already-landed batched evidence into the required one-record-per-step shape.

## Outcome

The checked row now has its own exec record. The matching anchor evidence for $anchor recorded codemod dry-run/apply, standalone review/workflow import probes, import sorting and formatting, and clean `pytest --collect-only -q src/aeat` for the 29-file batch. After the bulk scaffold pass, plan status reports xec_missing_ids is empty.

## Notes

Evidence-only reconciliation. The codebase has continued to evolve after the original W02 landing, so this record cites the historical landed evidence and does not claim a fresh source edit.
