---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:6429c2aefad64761eea6d188aa45da26a6859df2b1d491d1fafc9b782a3bb7cd'
step_id: 'S06'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# add the dual-mode enrollment recorder with calculation-based and non-calculation two-year-context capture (vaultspec-high-executor)

## Scope

- `src/aeat/application/calculations/_multi_year.py`

## Description

- Reconcile the stale-open dual-mode recorder row against current `_multi_year.py`.
- Ground the row with `uvx vaultspec-rag search "EnrollmentEvidence single year ValidationError multi year recorder distinct renta years test" --type code --limit 12` and `uvx vaultspec-rag search "modelo multiyear renta W01 P02 S06 S07 enrollment recorder exec" --doc-type exec --limit 12`.
- Confirm `EnrollmentRecorder.record_calculation_year()` records calculation-mode years only with a positive produced-value count.
- Confirm `EnrollmentRecorder.record_context_year()` records non-calculation context years only with a non-blank label and positive persisted-observation count.
- Update the plan scope to include the context-mode guard tests already defending this behavior.

## Outcome

- `src/aeat/application/calculations/_multi_year.py` implements the dual-mode recorder.
- `src/aeat/application/calculations/tests/test_enrollment_recorder_context_mode_guard.py` covers context-mode refusal and positive-path behavior.
- `uv run --no-sync pytest -q -n 0 src\aeat\application\calculations\tests\test_enrollment_recorder_context_mode_guard.py src\aeat\application\calculations\tests\test_multi_year_recorder.py`: 8 passed.
- No production source changed in this reconciliation pass.

## Notes

- This row is closed as already implemented at current HEAD.
