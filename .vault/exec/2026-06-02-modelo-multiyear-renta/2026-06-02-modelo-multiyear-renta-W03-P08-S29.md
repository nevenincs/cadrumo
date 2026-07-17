---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S29'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the 111->190 two-renta reconciliation enrollment test using real withholding feeder observations and annual manifest evidence

## Scope

- `src/aeat/application/calculations/tests/test_modelo_190_111_reconciliation_continuity.py`

## Description

- Rebaseline stale-open M190 reconciliation-test row against the current test suite.
- Ground the check with RAG-first W02-W03 discovery and targeted reads of the 111->190 reconciliation test.
- Update the plan row to the actual M190 reconciliation enrollment test path.

## Outcome

- `test_modelo_190_111_reconciliation_continuity.py` already records both M190 and feeder M111 evidence across 2025 and 2026, asserts relation aggregation, checks year isolation, and matches the manifest.
- The satisfied scope is monetary withholding reconciliation and two-year enrollment evidence.
- No product code changed in this step.

## Notes

- This does not claim quarterly perceptor counts are summed; `decl.total-percepciones` remains sourced from distinct withholding detail.
