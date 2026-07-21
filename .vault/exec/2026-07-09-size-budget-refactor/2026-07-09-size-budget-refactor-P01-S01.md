---
tags:
  - '#exec'
  - '#size-budget-refactor'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S01'
related:
  - "[[2026-07-09-size-budget-refactor-plan]]"
---

# Record the 6 over-budget module offenders and their owning campaign (secure_objects.py owner-surface, _iva_ledger.py prorrata, _calendar.py owner-surface, _commands.py mcp, _ledger_bindings.py prorrata, _models.py prorrata)

## Scope

- `src/aeat/tests/test_codebase_size_budgets.py`

## Description

- Ran `test_codebase_size_budgets.py` to enumerate the full offender inventory before authoring the plan.
- Recorded the 6 over-budget module offenders and their owning campaign: `secure_objects.py` (1312 > 1295, owner-surface), `_iva_ledger.py` (1617 > 1250, prorrata), `_calendar.py` (1677 > 1667, owner-surface), `_commands.py` (1339 > 1305, mcp), `_ledger_bindings.py` (1440 > 1400, prorrata), `_models.py` (1419 > 1340, prorrata).

## Outcome

Module-offender inventory confirmed and split by ownership, forming the basis of the plan's Phase structure (P02-P04 owner-surface, P05 deferred).

## Notes

No incidents.
