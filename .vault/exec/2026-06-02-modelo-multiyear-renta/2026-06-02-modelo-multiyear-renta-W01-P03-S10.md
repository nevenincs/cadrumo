---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:aca68e64cda1ce1637f48309a3302cb32126d36731db5550cf8a3bd3579f08ab'
step_id: 'S10'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# cross-check each recorded year-set equals the manifest renta_years claim, contains >=2 distinct years, and calls the enrollment contract (vaultspec-high-executor)

## Scope

- `src/aeat/tests/test_modelo_authorization_gate.py`

## Description

- Re-ran the authorization-gate module after the Modelo 145 fleet repair.
- Confirmed the manifest validity gate still rejects manifest entries outside the canonical fleet, fewer than two distinct renta years, missing enrolling tests, and tests that do not call `assert_enrollment_matches_manifest`.
- Confirmed the canonical fleet and live registry now agree at 73 entries, so the manifest cross-check iterates the honest denominator.

## Outcome

- `uv run --no-sync pytest -q -n 0 src\aeat\tests\test_modelo_authorization_gate.py`: 5 passed.
- `uv run --no-sync pytest -q -n 0 src\aeat\core\tests\test_modelo.py`: 5 passed.
- `uv run --no-sync pytest -q -n 0 src\aeat\application\overview\tests\test_obligation_coverage.py`: 10 passed.
- `uv run --no-sync ruff check src\aeat\core\_modelo.py src\aeat\tests\test_modelo_authorization_gate.py`: passed.

## Notes

- No manifest fragments were changed. Modelo 145 remains unauthorized by absence until a future enrollment step provides qualifying evidence.
