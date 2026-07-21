---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S63'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# write the M210 >=2-renta E2E test using two consecutive annual rental-income groupings via real adapters (vaultspec-high-executor)

## Scope

- `src/aeat/application/calculations/test_modelo_210_annual_continuity.py`

## Description

- Rebaseline the M210 annual-continuity enrollment surface against the live test tree.
- Confirm `test_modelo_210_irnr_continuity.py` records 2025 and 2026 calculation years through `EnrollmentRecorder`.
- Close the stale-open row without changing source code.

## Outcome

Closed as current-code satisfied. The current test is the real-adapter two-renta M210 enrollment test requested by the row, under its live filename.

## Notes

Verification: the focused W06/W07 stale-open test batch returned 42 passed. No skipped, xfailed, fake, or monkeypatched coverage was introduced.
