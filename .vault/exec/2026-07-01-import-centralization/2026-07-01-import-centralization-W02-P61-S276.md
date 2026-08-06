---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:19a6c0f9256fe5a756ab141426cd6b6c19bb2a3603c1356e9b6bac4a13c97717'
step_id: 'S276'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.contribuyente`

## Scope

- `src/aeat/domain/modelos/_work_unit.py`
## Description

- Reconcile $display as an individual exec record for a W02 production consumer-rewrite row already checked in the plan.
- Preserve the row intent: Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.contribuyente`.
- Tie this row to the domain model/transaction/attachment/deadline/fincas/invoice/IVA rewrite batch recorded by `W02.P61.S275` and landed in `1f292b29a`.
- Record no new implementation work; this document splits already-landed batched evidence into the required one-record-per-step shape.

## Outcome

The checked row now has its own exec record. The matching anchor evidence for $anchor recorded codemod dry-run/apply, import sorting and formatting, clean `pytest --collect-only -q src/aeat`, and a final scanner result of zero production sites needing facade promotion. After the bulk scaffold pass, plan status reports xec_missing_ids is empty.

## Notes

Evidence-only reconciliation. The codebase has continued to evolve after the original W02 landing, so this record cites the historical landed evidence and does not claim a fresh source edit.
