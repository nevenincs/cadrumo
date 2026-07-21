---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S25'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M100 two-renta enrollment test proving the general-base negative saldo wiring through real calculate and manifest evidence

## Scope

- `src/aeat/application/calculations/tests/test_modelo_100_multiyear_renta_enrollment.py`

## Description

- Rebaseline stale-open M100 enrollment-test row against the current test suite.
- Ground the check with RAG-first W02-W03 discovery and targeted reads of the M100 enrollment test.
- Update the plan row to the actual M100 multi-year enrollment test path.

## Outcome

- `test_modelo_100_multiyear_renta_enrollment.py` already drives real `calculate_modelo_revision` for two renta years, records produced values through `EnrollmentRecorder`, and checks the authorization manifest.
- The proof scope is M100 general-base `1391 -> 1388` wiring/provenance across 2024 and 2025.
- No product code changed in this step.

## Notes

- This does not claim the stale capital-loss wording from the old row or broader M100 carry completeness.
