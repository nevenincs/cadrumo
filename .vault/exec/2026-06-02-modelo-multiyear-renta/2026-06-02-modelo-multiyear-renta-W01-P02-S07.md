---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:7b16456a949086e184bd283fa7d9ef19e1ad656233279435ffcce47736632687'
step_id: 'S07'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# enforce the >=2-distinct-renta-years invariant at the pydantic type boundary so a malformed evidence record cannot construct (vaultspec-high-executor)

## Scope

- `src/aeat/application/calculations/_multi_year.py`
- `src/aeat/application/calculations/tests/test_multi_year_recorder.py`

## Description

- Reconcile the stale-open type-boundary invariant row against current `_multi_year.py`.
- Ground the row with `uvx vaultspec-rag search "EnrollmentEvidence single year ValidationError multi year recorder distinct renta years test" --type code --limit 12` and `uvx vaultspec-rag search "modelo multiyear renta W01 P02 S06 S07 enrollment recorder exec" --doc-type exec --limit 12`.
- Confirm `EnrollmentEvidence.model_post_init()` rejects evidence spanning fewer than the configured minimum distinct renta years.
- Confirm the direct anti-tautology test from S08 now pins the pydantic boundary, while this row records the implementation side of the same invariant.
- Update the plan scope to include the direct boundary test.

## Outcome

- `src/aeat/application/calculations/_multi_year.py` enforces the `>=2` distinct renta-year invariant at construction time.
- `src/aeat/application/calculations/tests/test_multi_year_recorder.py` proves single-year evidence raises `ValidationError` and two-year evidence constructs.
- `uv run --no-sync pytest -q -n 0 src\aeat\application\calculations\tests\test_enrollment_recorder_context_mode_guard.py src\aeat\application\calculations\tests\test_multi_year_recorder.py`: 8 passed.
- No production source changed in this reconciliation pass.

## Notes

- This row is closed as already implemented at current HEAD. S08 remains the direct test ratchet; this S07 record closes the implementation row.
