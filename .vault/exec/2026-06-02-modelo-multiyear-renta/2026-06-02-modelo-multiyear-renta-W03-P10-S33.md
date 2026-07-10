---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S33'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the 123->193 two-renta reconciliation enrollment test using real capital-mobiliario feeder observations and annual manifest evidence

## Scope

- `src/aeat/application/calculations/tests/test_modelo_193_123_reconciliation_continuity.py`

## Description

- Rebaseline stale-open M193 reconciliation-test row against the current test suite.
- Ground the check with RAG-first W02-W03 discovery and targeted reads of the 123->193 reconciliation test.
- Update the plan row to the actual M193 reconciliation enrollment test path.

## Outcome

- `test_modelo_193_123_reconciliation_continuity.py` already records both M193 and feeder M123 evidence across 2025 and 2026, asserts monetary base/retenciones fold-in, checks year isolation, and matches the manifest.
- The satisfied scope is capital-mobiliario withholding reconciliation and two-year enrollment evidence.
- No product code changed in this step.

## Notes

- This does not claim perceptor-count aggregation is proved by the current test.
