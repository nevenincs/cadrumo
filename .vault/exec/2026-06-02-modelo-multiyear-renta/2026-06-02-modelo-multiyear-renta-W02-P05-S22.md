---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:c0b5f27ec37195be1aa2fd28c1c90afbfd383be95ca7d448fe6f5d8dd3d67084'
step_id: 'S22'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M130 multi-year enrollment test that drives two renta years through real adapters and records the manifest-matched filing_year set

## Scope

- `src/aeat/application/calculations/tests/test_modelo_130_multiyear_renta_enrollment.py`

## Description

- Rebaseline stale-open M130 test row against the current codebase.
- Ground the check with `uvx vaultspec-rag search "Modelo 130 carry forward continuity second renta year recorder captures two filing years real adapters" --type code --limit 10`.
- Update the plan row to the current dedicated enrollment test path.

## Outcome

- `test_modelo_130_multiyear_renta_enrollment.py` already drives the real M130 backend across two distinct renta years, records both years through `EnrollmentRecorder.record_calculation_year`, asserts the recorded year-set, and calls `assert_enrollment_matches_manifest`.
- The test uses real encrypted SQLite repositories, the real registry authority, the real previous_filing binding resolver, and the real registry calculation engine.
- The original row's target file was stale: the cross-renta enrollment proof now lives beside, not inside, the quarter-to-quarter carry-forward continuity test.

## Notes

- This closes the M130 enrollment-test evidence row only. It does not claim any new M130 code was authored in this slice.
