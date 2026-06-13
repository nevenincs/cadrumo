---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S183'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s183-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S183`

Closed `AFR-081` for the runtime-owned secure-object repository factories.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/runtime_repository.py` against the `runtime-default` contract.
- Kept active-profile and named-bucket factories routed through storage runtime readiness.
- Promoted the shared runtime not-ready error constructor to the public adapter runtime surface.
- Routed missing active-profile factory failures through localized runtime not-ready details.
- Added a real-behavior regression test for the missing active-profile factory path.
- Closed `AFR-081` and `W12.P26.S183`.

## Outcome

`AFR-081` is closed. Runtime repository factories still fail closed for active profile/session mismatches, the cold/default bootstrap exceptions remain explicit, and the missing active-profile path now emits a localized `StorageValidationError` with runtime details.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/runtime.py src/aeat/adapters/persistence/storage/runtime_repository.py src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

Plain `uv run --no-sync python -m aeat.locales audit` could not import `aeat` after concurrent packaging changes because the project package was not installed into the active `.venv`; running the same mandated CLI with `PYTHONPATH=src` avoided environment mutation. A non-`--no-sync` install attempt was blocked by a locked `vaultspec-rag.exe` in the shared `.venv`.

Post-step plan check could not run because `uv run --no-sync vaultspec-core ...` failed to spawn `vaultspec-core` even though the package remains declared in `pyproject.toml` and `uv.lock`. The step close command succeeded before that tooling regression surfaced.
