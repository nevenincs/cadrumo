---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S31'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the 115->180 two-renta reconciliation enrollment test using real arrendamiento feeder observations and annual manifest evidence

## Scope

- `src/aeat/application/calculations/tests/test_modelo_180_115_reconciliation_continuity.py`

## Description

- Rebaseline stale-open M180 reconciliation-test row against the current test suite.
- Ground the check with RAG-first W02-W03 discovery and targeted reads of the 115->180 reconciliation test.
- Update the plan row to the actual M180 reconciliation enrollment test path.

## Outcome

- `test_modelo_180_115_reconciliation_continuity.py` already records both M180 and feeder M115 evidence across 2025 and 2026, asserts relation sums, checks year isolation, and matches the manifest.
- The satisfied scope is arrendamiento withholding reconciliation and two-year enrollment evidence.
- No product code changed in this step.

## Notes

- This does not claim `decl.total-perceptores` is validated by summing quarterly M115 counts; that is outside the current assertion path.
