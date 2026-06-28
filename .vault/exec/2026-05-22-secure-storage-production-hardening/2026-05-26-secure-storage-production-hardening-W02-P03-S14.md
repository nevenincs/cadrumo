---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S14'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---



# `secure-storage-production-hardening` `W02.P03.S14`

Routed state-projection workspace reads through runtime readiness and removed env-backed test isolation from the projection suite.

- Modified: `src/aeat/application/state_projection.py`
- Modified: `src/aeat/application/test_state_projection.py`
- Modified: `src/aeat/core/errors/registry/_adapters.py`
- Modified: `src/aeat/adapters/persistence/storage/errors.py`
- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/es.yml`
- Modified: `src/aeat/locales/ca.yml`
- Modified: `src/aeat/locales/hu.yml`
- Created: `.vault/exec/2026-05-22-secure-storage-production-hardening/2026-05-26-secure-storage-production-hardening-W02-P03-S14.md`

## Description

The workspace summary path now calls `inspect_bucket_storage_runtime(bucket_id).require_ready()` before loading transaction, invoice, draft, work-unit, revision, or secure-object unreadability counters. This makes the projection fail closed through the same runtime readiness boundary as the profile repository work in the previous step.

The projection tests now isolate storage through `override_settings(aeat_local_storage_root=..., aeat_active_profile=None)` and `EphemeralMasterKeyProvider`, removing direct environment mutation from the fixture while preserving real SQLite, filesystem, and repository behavior.

The broader verification run exposed an in-flight registry blocker for the new `SecureStorageError` base class. The registry now declares `FAIL_SECURE_STORAGE`, and the locale files were updated and validated through `uv run python -m aeat.locales scaffold` and `uv run python -m aeat.locales audit`.

## Tests

`uv run ruff check src/aeat/application/state_projection.py src/aeat/application/test_state_projection.py src/aeat/core/errors/registry/_adapters.py src/aeat/adapters/persistence/storage/errors.py src/aeat/application/user_profile/_repository.py src/aeat/application/user_profile/test_repository.py src/aeat/adapters/persistence/storage/runtime.py src/aeat/adapters/persistence/storage/test_runtime.py` passed.

`uv run pytest src/aeat/core/errors/test_registry_enforcement.py src/aeat/application/test_state_projection.py src/aeat/application/user_profile/test_repository.py src/aeat/adapters/persistence/storage/test_runtime.py -q` reported 43 passed.

`uv run python -m aeat.locales audit` reported `ok` for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
