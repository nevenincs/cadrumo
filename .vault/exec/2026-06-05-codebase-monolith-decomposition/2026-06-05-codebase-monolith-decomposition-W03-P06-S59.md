---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S59'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P06.S59 Auth Operator Decomposition

Scope: `src/aeat/application/auth/_operator.py`, `src/aeat/application/auth/_operator_results.py`, `src/aeat/application/auth/_operator_probes.py`, `src/aeat/application/auth/_operator_scope.py`, `src/aeat/application/auth/__init__.py`.

## Description

- Used RAG and direct symbol discovery to inspect the auth operator surface.
- Kept `aeat.application.auth` as the public facade for consumers.
- Moved operator result/error contracts into `_operator_results.py` and updated the central error registry class paths.
- Moved local provider and persisted-session probes into `_operator_probes.py`.
- Moved auth settings and active-profile storage scopes into `_operator_scope.py`.
- Repaired the public auth facade so operator actions remain exported from `_operator.py` and DTO/error contracts remain exported through `aeat.application.auth`.

## Outcome

`src/aeat/application/auth/_operator.py` is now 815 lines, below the 1250-line monolith budget, while retaining the public auth facade contract.

## Verification

- `uv run --no-sync vaultspec-rag search "auth operator result contracts probes storage scope decomposition public auth facade" --type code --path src/aeat/application/auth/_operator.py --max-results 8 --port 8766 --json` completed.
- `uv run --no-sync ruff check src/aeat/application/auth/_operator.py src/aeat/application/auth/_operator_results.py src/aeat/application/auth/_operator_probes.py src/aeat/application/auth/_operator_scope.py src/aeat/application/tests/test_error_class_registration.py src/aeat/core/errors/registry/_application.py src/aeat/tests/test_codebase_size_budgets.py` passed.
- `uv run --no-sync pytest -q -m "unit or integration" src/aeat/application/auth/tests src/aeat/entrypoints/cli/_config/tests/test_auth_round5_surface.py src/aeat/application/tests/test_error_class_registration.py` passed: 115 tests.

## Notes

The auth verification row S60 remains responsible for focused auth application and config CLI behavior tests.
