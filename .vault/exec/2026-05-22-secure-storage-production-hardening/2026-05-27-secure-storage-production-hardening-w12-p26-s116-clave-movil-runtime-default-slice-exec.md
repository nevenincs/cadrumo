---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S116'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening` `W12.P26.S116` Clave Movil Runtime-Default Slice

Closed `AFR-014` for the Clave Movil adapter by routing encrypted diagnostic writes through the active bucket storage runtime.

## Changes

- Replaced the `_dump_diagnostic` direct `SecureObjectRepository()` write with `secure_object_repository_for_active_bucket()`.
- Preserved the diagnostic payload shape, SESSION classification, schema version, object key, best-effort capture behavior, and warning log on capture failure.
- Strengthened the failure-path test to prove the diagnostic id returned in the auth exception maps to a real encrypted SESSION row in the active bucket.
- Closed the file-level plan row with `uv run vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md S116` and marked `AFR-014` as migrated in the audit register.

## Validation

- `uv run pytest src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py::TestPendingPetitionRefusal::test_pending_petition_page_fails_fast_with_actionable_mode src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py::TestClaveWaitState::test_login_refuses_to_wait_without_observed_confirmation_state src/aeat/application/auth/test_diagnostics.py -q` - 3 passed.
- `uv run ruff check src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/application/auth/test_diagnostics.py` - passed.
- `rg -n "SecureObjectRepository\\(" src/aeat/adapters/outbound/aeat/auth/_clave_movil.py` - no remaining direct constructor hits.
- Focused code review re-review reported no findings.
- `uv run vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` - passed.

## Residual Debt

- The broader `W12.P21.S86` outbound-adapter runtime-default rollout may still include non-constructor storage and master-key surfaces outside this diagnostic writer.

## Tracking

Completed internal tasklist for this slice:

- Select `AFR-014` as the next clean outbound direct-constructor target: complete.
- Bind Clave Movil diagnostic writes to the active bucket runtime repository: complete.
- Preserve best-effort diagnostic capture semantics: complete.
- Add a real encrypted persistence assertion for the migrated writer: complete.
- Verify focused tests, lint, constructor inventory, plan row closure, and review: complete.
