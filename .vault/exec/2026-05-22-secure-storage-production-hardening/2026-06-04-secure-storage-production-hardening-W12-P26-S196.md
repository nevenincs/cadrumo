---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S196'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s196-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S196`

Closed `AFR-094` for the apoderado auth service.

## Description

- Reviewed `src/aeat/application/auth/_apoderado.py` against the
  `runtime-default` secure-object classification.
- Extended `SecureBoundRepository` so explicit `Settings` can be passed through
  to runtime repository factories.
- Threaded `ApoderadoService._settings` into `_ApoderadoConfigRepository`
  construction.
- Added apoderado runtime-default refusal coverage to the migrated repository
  guard suite.
- Added an apoderado service test proving explicit settings are honored despite
  a conflicting context override.

## Outcome

`AFR-094` is closed. Apoderado configuration remains encrypted and bucket-bound,
and explicit service settings now control secure-storage routing instead of
being shadowed by process-global settings.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/auth/_apoderado.py src/aeat/application/auth/test_apoderado.py src/aeat/adapters/persistence/storage/envelope/_secure_repository.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py`
- `uv run --no-sync pytest -q src/aeat/application/auth/test_apoderado.py`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository.py`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No direct secure-object repository construction, naked environment access,
monkeypatches, fakes, mocks, skips, or xfails were introduced.
