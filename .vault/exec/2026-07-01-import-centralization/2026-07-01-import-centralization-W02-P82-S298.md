---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S298'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 6 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.calculations.registry`

## Scope

- `src/aeat/locales/_modelo_manager.py`
## Description

- Reconcile $display as an individual exec record for a W02 production consumer-rewrite row already checked in the plan.
- Preserve the row intent: Rewire 6 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.calculations.registry`.
- Tie this row to the `locales._modelo_manager` registry-loader consumer rewrite absorbed by the W01 loader-disposition sweep, landed in `b04fb67c25` and reconciled in the W01 registry-loader records.
- Record no new implementation work; this document splits already-landed batched evidence into the required one-record-per-step shape.

## Outcome

The checked row now has its own exec record. The matching anchor evidence for $anchor recorded the W01 tail import probes, ruff checks, targeted package tests, and clean final W01 collect-only evidence. After the bulk scaffold pass, plan status reports xec_missing_ids is empty.

## Notes

Evidence-only reconciliation. This W02 row had no separate W02 codemod commit because the private registry-loader reach was removed while defining the narrower public loader API in W01.
