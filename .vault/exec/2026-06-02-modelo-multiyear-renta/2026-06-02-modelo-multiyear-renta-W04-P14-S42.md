---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S42'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M353 two-renta aggregation enrollment test summing two members real 322 calculations into 353

## Scope

- `src/aeat/application/calculations/tests/test_modelo_353_grupo_aggregation_continuity.py`

## Description

- Rebaseline stale-open M353 enrollment-test row against the current test suite.
- Ground the check with RAG-first W04-W05 discovery and targeted reads of the M353 aggregation test.
- Update the plan row to the actual M353 two-member aggregation proof.

## Outcome

- `test_modelo_353_grupo_aggregation_continuity.py` already proves two members' real M322 calculations are summed into M353 for 2025 and 2026.
- No product code changed in this step.

## Notes

- This does not claim the stale manifest-comment scenario of `12/2025` into `01/2026`; the current proof uses period `12` in both years.
