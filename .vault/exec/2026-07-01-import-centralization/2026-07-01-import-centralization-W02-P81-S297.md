---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:109277a319fe468d5ce132a8714e34659809b61ff8d09c96c6bab1f725259b43'
step_id: 'S297'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 7 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.contribuyente`, `aeat.domain.deadlines`

## Scope

- `src/aeat/locales/_fstring_registry.py`
## Description

- Reconcile $display as an individual exec record for a W02 production consumer-rewrite row already checked in the plan.
- Preserve the row intent: Rewire 7 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.contribuyente`, `aeat.domain.deadlines`.
- Tie this row to the core/resources/observability/config/logging/locales rewrite batch recorded by `W02.P54.S258` and landed in `563dece0e`.
- Record no new implementation work; this document splits already-landed batched evidence into the required one-record-per-step shape.

## Outcome

The checked row now has its own exec record. The matching anchor evidence for $anchor recorded codemod dry-run/apply, import sorting and formatting, and clean `pytest --collect-only -q src/aeat` for the 10-file batch. After the bulk scaffold pass, plan status reports xec_missing_ids is empty.

## Notes

Evidence-only reconciliation. The codebase has continued to evolve after the original W02 landing, so this record cites the historical landed evidence and does not claim a fresh source edit.
