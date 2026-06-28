---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S71'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P07.S71 Registry Workbook Parity Decomposition

Scope: `src/aeat/domain/calculations/registry/_workbook_parity.py src/aeat/domain/calculations/registry/*.py`.

## Description

- Extract the closed workbook parity vocabulary from `_workbook_parity.py` into `_workbook_parity_types.py`.
- Extract workbook parity Pydantic data contracts from `_workbook_parity.py` into `_workbook_parity_models.py`.
- Keep `_workbook_parity.py` importing and re-exporting workbook parity status, kind, engine, parity result types, reports, and synthetic input contracts for existing callers.
- Preserve operational workbook parity scan, conversion, runner, comparison, and backend verification behavior in `_workbook_parity.py`.

## Outcome

Workbook parity status and engine vocabulary now live in a focused private types module, and workbook parity report/input contracts now live in a focused private models module. The scan, conversion, runner, comparison, and verification logic remains in `_workbook_parity.py`, which is now 1076 lines.

## Notes

No consumer-facing import path changed. No behavior skips, fakes, mocks, monkeypatches, or xfails were introduced.
