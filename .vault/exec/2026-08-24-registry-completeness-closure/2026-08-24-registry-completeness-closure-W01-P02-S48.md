---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:e27bb8f462097a7c19317b79989d57341dd2739d396cf0e53479c9d7e0cf3730'
step_id: 'S48'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# Prove undeclared-grade refusals reject a non-null declared grade through direct construction and revalidated mutation.

## Scope

- `src/cadrumo/application/registry/tests/`

## Description

- Add a direct-construction contradiction in `test_temporal_coverage.py`: an `undeclared_authority_grade` refusal carrying applicability grade must fail validation.
- Add the same contradiction through `model_copy` followed by `model_validate`, proving public deserialisation re-applies the invariant to a mutated frozen row.
- Exercise an isolated guardless copy of `_temporal_coverage.py`; the direct and revalidated contradictions were both accepted and the external proof deliberately failed, confirming the two new cases bite.
- Run focused Ruff and temporal-coverage pytest checks.

## Outcome

The two public construction paths now prove that an undeclared-grade refusal cannot simultaneously report a declared authority grade. Removing only that guard admits both contradictory inputs in an isolated copy, so the regression proof is specific to the required invariant.

## Notes

`uv run --no-sync ruff check src/cadrumo/application/registry/tests/test_temporal_coverage.py` passed. `uv run --no-sync pytest -n 0 -q src/cadrumo/application/registry/tests/test_temporal_coverage.py` passed with 28 tests. The isolated guardless run intentionally exited non-zero with `AssertionError: guardless copy accepted direct and revalidated undeclared-grade contradictions`; no tracked production file was modified.
