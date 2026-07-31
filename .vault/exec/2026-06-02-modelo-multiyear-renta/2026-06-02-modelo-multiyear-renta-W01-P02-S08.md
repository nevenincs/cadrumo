---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:4961fb7c2f6adf55cb9a849f341dfffd4ec6a633331ce7481dbb665b99db8844'
step_id: 'S08'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# write an anti-tautology test proving a single-year evidence record raises ValidationError (vaultspec-standard-executor)

## Scope

- `src/aeat/application/calculations/tests/test_multi_year_recorder.py`

## Description

- Ground the missing direct type-boundary proof with `uvx vaultspec-rag search "EnrollmentEvidence single year ValidationError multi year recorder distinct renta years test" --type code --limit 12`.
- Added `test_enrollment_evidence_rejects_single_distinct_renta_year`, constructing a real `EnrollmentYearObservation` and asserting direct `EnrollmentEvidence` construction raises `pydantic.ValidationError` for a single renta year.
- Added a positive control proving two distinct years construct successfully and report the sorted `(2024, 2025)` year tuple.
- Left `_multi_year.py` unchanged because the existing type boundary already enforced the invariant.

## Outcome

- `uv run --no-sync pytest -q -n 0 src\aeat\application\calculations\tests\test_multi_year_recorder.py`: 2 passed.
- `uv run --no-sync pytest -q -n 0 src\aeat\application\calculations\tests\test_enrollment_recorder_context_mode_guard.py src\aeat\application\calculations\tests\test_multi_year_recorder.py`: 8 passed.
- `uv run --no-sync ruff check src\aeat\application\calculations\tests\test_multi_year_recorder.py`: passed.
- Independent `vaultspec-code-reviewer` review found no blocking findings.

## Notes

- Full repository tests were not run because the shared worktree carries broad unrelated WIP.
- Residual recorder-path evidence capture and non-calculation context-mode coverage remain in separate plan scope under S06, S07, S88, and later enrollment E2E rows.
