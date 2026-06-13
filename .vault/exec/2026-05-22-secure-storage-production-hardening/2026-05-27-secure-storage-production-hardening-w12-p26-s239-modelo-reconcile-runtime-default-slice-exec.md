---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S239'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening` `W12.P26.S239` Modelo Reconcile Runtime-Default Slice

Closed `AFR-137` for modelo reconciliation by routing bucket-event persistence through the runtime-owned repository already used by the service.

## Changes

- Removed the local direct `SecureObjectRepository` import from `modelo_reconcile`.
- Replaced the raw `save_many` call with `BucketEventHistoryRepository.save(next_catalogue)`.
- Preserved the existing load, append, payload, event-id, actor, and verdict behavior while centralizing the write path in the bucket-event repository.
- Closed the file-level plan row with `uv run vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md S239` and marked `AFR-137` as migrated in the audit register.

## Validation

- `uv run pytest src/aeat/application/modelo/test_reconcile.py -q` - 7 passed.
- `uv run pytest src/aeat/entrypoints/cli/test_modelo_reconcile_verb.py::test_reconcile_by_flag_lands_in_modelo_reconciled_event src/aeat/entrypoints/cli/test_modelo_reconcile_verb.py::test_reconcile_happy_path_against_justificante -q` - 2 passed.
- `uv run ruff check src/aeat/application/modelo/_reconcile.py src/aeat/application/modelo/test_reconcile.py src/aeat/entrypoints/cli/test_modelo_reconcile_verb.py` - passed.
- `rg -n "SecureObjectRepository\\(" src/aeat/application/modelo/_reconcile.py` - no remaining direct constructor hits.
- Focused code review reported no findings.

## Residual Debt

- The broader `W12.P21.S85` application runtime-default rollout still includes diagnostics and repair-integrity direct-constructor surfaces.

## Tracking

Completed internal tasklist for this slice:

- Select `AFR-137` as the next clean application direct-constructor target: complete.
- Replace raw secure-object persistence with the domain bucket-event repository API: complete.
- Preserve reconciliation event semantics and actor threading: complete.
- Verify application, CLI, lint, constructor inventory, plan row closure, and review: complete.
