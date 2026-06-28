---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S19'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-production-hardening-w02-p04-s19-review-audit]]'
---

# `secure-storage-production-hardening` `W02.P04.S19`

Added a policy guard against direct production `SecureObjectRepository` construction.

- Modified: `src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py`
- Modified: `src/aeat/application/auth/_operator.py`
- Modified: `src/aeat/application/auth/test_operator.py`
- Modified: `src/aeat/entrypoints/cli/_config/_google.py`

## Description

The storage hardening convention guard now walks production Python sources and rejects `SecureObjectRepository` construction outside the runtime owner. It resolves direct constructor imports, import aliases, simple local aliases, and SQL module aliases, while allowing only `src/aeat/adapters/persistence/storage/runtime.py` to construct the repository with an explicit non-`None` engine.

The remaining production callers in the S19 slice now use `secure_object_repository_for_active_bucket()` instead of constructing ambient repositories. Auth operator tests were moved onto an active bucket session and settings override so the migrated write path exercises the runtime route.

## Tests

- `uv run ruff check` on the S19 implementation and focused tests: passed.
- `uv run pytest src/aeat/application/auth/test_operator.py src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py -q`: `28 passed`, with one existing pytest collection warning for imported production function `test_operator_auth`.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`: passed.
- `uv run python -m aeat.locales audit`: invoked as required; failed on unrelated `hu.yml` parity gaps already present in the shared worktree.
- Code review recorded in `2026-05-26-secure-storage-production-hardening-W02-P04-S19-review-audit.md`; no HIGH or CRITICAL issues remain.
