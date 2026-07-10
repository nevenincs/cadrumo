---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-05'
modified: '2026-07-08'
step_id: 'S175'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 14 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.modelo`, `aeat.domain.modelos`, `aeat.domain.transactions`, `aeat.domain.user_profile`

## Scope

- `src/aeat/application/user_profile/_bundle.py`
## Description

- Reconcile $display as an individual exec record for a W02 production consumer-rewrite row already checked in the plan.
- Preserve the row intent: Rewire 14 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.modelo`, `aeat.domain.modelos`, `aeat.domain.transactions`, `aeat.domain.user_profile`.
- Tie this row to the user-profile / contribuyente rewrite batch recorded by `W02.P41.S174` and landed in `176dbebd1`.
- Record no new implementation work; this document splits already-landed batched evidence into the required one-record-per-step shape.

## Outcome

The checked row now has its own exec record. The matching anchor evidence for $anchor recorded codemod dry-run/apply, hand rewrites to public parsing aliases, import sorting and formatting, and clean `pytest --collect-only -q src/aeat` for the 19-file batch. After the bulk scaffold pass, plan status reports xec_missing_ids is empty.

## Notes

Evidence-only reconciliation. The codebase has continued to evolve after the original W02 landing, so this record cites the historical landed evidence and does not claim a fresh source edit.
