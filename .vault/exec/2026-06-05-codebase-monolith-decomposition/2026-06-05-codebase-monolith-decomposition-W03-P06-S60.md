---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S60'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P06.S60 Auth Operator Verification

Scope: `src/aeat/application/auth/tests`, `src/aeat/entrypoints/cli/_config/tests`, `src/aeat/application/auth`, `src/aeat/core/errors/registry`.

## Description

- Verified the auth operator decomposition after splitting result contracts, provider probes, and storage scopes out of `_operator.py`.
- Confirmed `aeat.application.auth` remains the public facade for operator actions and result/error contracts.
- Confirmed moved auth operator error classes bind through the application error-code registry under their new module path.

## Verification

- `uv run --no-sync ruff check src/aeat/application/tests/test_error_class_registration.py src/aeat/tests/test_codebase_size_budgets.py` passed.
- `uv run --no-sync pytest -q -m "unit or integration" src/aeat/application/tests/test_error_class_registration.py src/aeat/tests/test_codebase_size_budgets.py src/aeat/tests/test_marker_integrity.py` passed: 2,100 tests.
- `uv run --no-sync pytest -q -m "unit or integration" src/aeat/application/auth/tests src/aeat/entrypoints/cli/_config/tests/test_auth_round5_surface.py` passed: 98 tests.

## Outcome

S60 verification passed. `_operator.py` remains below the 1250-line budget, and auth consumers continue to use `aeat.application.auth` as the facade.
