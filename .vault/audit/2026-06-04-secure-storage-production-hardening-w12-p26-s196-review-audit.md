---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S196]]'
---

# `secure-storage-production-hardening` `W12.P26.S196` Review

## S196-001 | FIXED | Explicit service settings reach secure storage runtime

`ApoderadoService(settings=...)` previously stored the explicit `Settings`
object but `_repository_for()` constructed `_ApoderadoConfigRepository` with only
`bucket_id`, causing `SecureBoundRepository` to fall back to process
`load_settings()`. The fix lets `SecureBoundRepository` accept optional
`settings` and forwards them into runtime repository factories; apoderado now
passes `self._settings` when building the bucket-bound repository.

## S196-002 | PASS | Secure-object ownership remains runtime-bound

The apoderado configuration continues to persist through
`SecureBoundRepository` in the `aeat.auth.apoderado` namespace with
`SensitivityClass.IDENTITY`. No direct `SecureObjectRepository` construction,
explicit database URL handling, naked environment access, or plaintext fallback
was introduced.

## S196-003 | PASS | Runtime-default refusal is covered

`test_runtime_migrated_repositories.py` now includes `auth_apoderado` in both
missing-session and route/session-mismatch runtime-default refusal gates. The
apoderado service test also proves explicit settings survive a conflicting
context override and do not write to the wrong storage root.

## S196-004 | PASS | Tests remain real-behavior

The new coverage uses real `isolated_runtime_profile`, real settings overrides,
and the shared runtime repository path. No fakes, mocks, monkeypatches, skips,
xfails, or mirrored business logic were added.

Validation:

- `uv run --no-sync ruff check src/aeat/application/auth/_apoderado.py src/aeat/application/auth/test_apoderado.py src/aeat/adapters/persistence/storage/envelope/_secure_repository.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/auth/test_apoderado.py` passed with 13 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository.py` passed with 9 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py` passed with 79 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

Reviewer note: subagent review remains unavailable because the reviewer agent hit
the account usage limit earlier in this run. Host review found no remaining
critical, high, medium, or low findings in the S196 slice.

Disposition: close `AFR-094`.
