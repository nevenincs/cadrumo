---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S27'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M131 modules continuity enrollment test across two renta years via real adapters and manifest evidence

## Scope

- `src/aeat/application/calculations/tests/test_modelo_131_carry_forward_continuity.py`

## Description

- Rebaseline stale-open M131 enrollment-test row against the current test suite.
- Ground the check with RAG-first W02-W03 discovery and targeted reads of the M131 continuity test.
- Update the plan row to the actual M131 test path.

## Outcome

- `test_modelo_131_carry_forward_continuity.py` already enrolls M131 across two renta years with real adapters, `EnrollmentRecorder`, and manifest matching.
- The satisfied scope is the current modules-continuity enrollment proof for 2024 and 2025.
- No product code changed in this step.

## Notes

- This does not claim a 4T-to-1T cross-year carry or full module coefficient calculation; the current test notes that cross-year carry remains blocked by the registry year-delta limit.
