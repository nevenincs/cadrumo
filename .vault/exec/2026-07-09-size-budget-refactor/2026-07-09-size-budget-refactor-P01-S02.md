---
tags:
  - '#exec'
  - '#size-budget-refactor'
date: '2026-07-09'
modified: '2026-07-17'
step_id: 'S02'
related:
  - "[[2026-07-09-size-budget-refactor-plan]]"
---

# Record the 6 over-budget callable offenders and their owning campaign (_classify_iva_transaction prorrata, build_overview_calendar owner-surface, taxpayer_profile_from_mapping owner-surface, ledger_add prorrata, build_server mcp, _call_tool mcp)

## Scope

- `src/aeat/tests/test_codebase_size_budgets.py`

## Description

- Recorded the 6 over-budget callable offenders and their owning campaign from the same `test_codebase_size_budgets.py` run: `_classify_iva_transaction` (208 > 180, prorrata), `build_overview_calendar` (202 > 192, owner-surface), `taxpayer_profile_from_mapping` (196 > 180, owner-surface), `ledger_add` (238 > 198, prorrata), `build_server` (510 > 341, mcp), `_call_tool` (209 > 180, mcp).

## Outcome

Callable-offender inventory confirmed and split by ownership, forming the basis of the plan's Phase structure.

## Notes

No incidents.
