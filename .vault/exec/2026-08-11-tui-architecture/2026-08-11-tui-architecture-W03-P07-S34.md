---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:def4abb52bddc290ba3f938600fcdb2d1b9bf23f1b8184238d8c8f017eea5d21'
step_id: 'S34'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Implement the recorded filed-history executor across discovery, register access, pair walk, capture, persistence, finalization, provenance, wallet, notifications, and settlement

## Scope

- `src/cadrumo/application/live/_filed_history_operation.py`
- `src/cadrumo/application/live/_filed_data_capture.py`
- `src/cadrumo/application/live/_remote_state_models.py`
- `src/cadrumo/application/storage/sync_runs/_records.py`
- `src/cadrumo/application/storage/sync_runs/__init__.py`
- `src/cadrumo/application/live/tests/test_filed_history_operation_executor.py`

## Description

- Add the immutable filed-history operation request and dependency-composed definition builder.
- Delegate discovery, register access, pair walk, capture, persistence, finalization, sync-run provenance, IVA wallet reconciliation, and notifications to the existing `pull_filed_history` authority.
- Declare recorded durability, idempotent submission, unsupported cancellation and deadline behavior, interrupt-on-owner-loss reconciliation, and the complete permitted effect set.
- Preserve `record_sync_run` as the single sync-run writer while exposing its existing encrypted-store key as a typed, domain-owned `SyncRunRecordReference`.
- Retain that resolvable reference on the bulk-capture and filed-history onboarding results, then return the same reference from the operation executor without reconstructing an identifier or performing a second write.
- Keep concrete sync-run persistence construction outside the application package by accepting its public application port at composition time.
- Validate the executor through the production supervisor, real encrypted secure-reference repository, real filesystem journal and lease adapters, and a real encrypted sync-run persistence roundtrip.

## Outcome

The filed-history workflow now has one frontend-neutral recorded executor and operation definition factory. The executor binds the active profile subject, preserves the existing business and write authorities, records preflight, execution, and settlement boundaries, and reports only effect states proved by the canonical result.

The canonical filed-history result boundary now retains the exact stable key of the `SyncRunRecord` written by `record_sync_run`. The executor returns that domain reference, and the integration proof resolves it through the real encrypted repository back to the same persisted sync-run record. No synthetic operation token, reconstructed child identity, or duplicate persistence path remains.

Focused validation passed with three sequential operation/persistence integration tests, 46 adjacent filed-history and sync-run tests, Ruff formatting and lint, BasedPyright, and diff-integrity checks.

## Notes

Dry-run exposure and parity remain owned by S35. Ordered per-stage and per-unit progress remain owned by S36. Public live-facade export remains owned by S37. S38 still owns the supervisor child-provenance join proof, but now receives a real resolvable domain reference from the S34 result boundary rather than having to reconstruct one.
