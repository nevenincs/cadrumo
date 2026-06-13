---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S183]]'
---

# `secure-storage-production-hardening` `W12.P26.S183` Review

## S183-001 | PASS | Repository factories stay runtime-owned

Bucket-specific and active-profile repository construction routes through the storage runtime readiness boundary before returning a `SecureObjectRepository`. The only direct constructors remain in the approved runtime files and bind an explicit engine, which is covered by the convention guard.

## S183-002 | PASS | Missing active profile uses localized runtime details

`secure_object_repository_for_active_bucket()` now raises the shared runtime not-ready error when no active profile bucket is selected. The error remains a `StorageValidationError`, carries `errors.storage.runtime.not_ready`, and includes localized details instead of an empty translated-message-only exception.

## S183-003 | PASS | Runtime not-ready helper is public at the adapter boundary

The reusable not-ready constructor is exported as `runtime_not_ready_error`, avoiding a new production import of a private helper across modules. Existing internal runtime calls keep the compatibility alias.

## S183-004 | PASS | Tests exercise observable behavior

The added test exercises the public active-bucket factory under real settings override and resolves the rendered error message. It does not use mocks, monkeypatching, fakes, stubs, skips, xfails, or mirrored business logic.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py` passed with 39 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/runtime.py src/aeat/adapters/persistence/storage/runtime_repository.py src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py` passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` failed to spawn `vaultspec-core`; this is tracked as a tooling gate failure and was not treated as a blocker per user instruction.
- Scoped hygiene scans found no private runtime-helper import, naked environment access, monkeypatch/fake/stub shortcuts, skips/xfails, silent pass/suppress, or ignore pragmas.

Review-agent note: spawning `vaultspec-code-reviewer` remains unavailable in this session due the agent thread limit, so the supervisor completed the same checklist locally.

Disposition: close `AFR-081`.
