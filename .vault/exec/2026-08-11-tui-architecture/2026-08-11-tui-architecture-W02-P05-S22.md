---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:1f9346dea2a84f2da4f09f8cff2dc45d8a77d504813e2e9efc997955a415097e'
step_id: 'S22'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# W02.P05.S22 - Implement the durable operation supervisor vertical slice

## Scope

Implement submit, start, inspect, observe, await, respond, reject, request-cancel, detach, settle, and reconcile operations with durable idempotency, exact interaction and lease correlation, definition-bound mutation checks, secure references, and journal compare-and-swap invariants.

## Description

- Ground the supervisor, interaction, idempotency, cleanup-family, secure-reference, and conflict-scope concepts through live code and vault semantic searches, whole-file epicenter reads, and targeted symbol confirmation.
- Extend the canonical operation contracts with credential-free schema-v2 checkpoints, safe interaction events, deterministic conflict-scope references, and strict secure-reference custody.
- Implement the encrypted content-addressed secure-reference repository over the registered secure-object authority.
- Migrate durable lease storage to scope-keyed schema v2 with explicit acquisition-only legacy adjudication and exact scope-plus-operation evidence.
- Implement `OperationSupervisor` and its definition-bound executor context, refusing undeclared phase, effect, interaction, and cleanup-family mutations before those mutations occur.
- Persist a safe start event, pending/consumed interaction checkpoints, exact single-use response evidence, and idempotency claims through canonical journal compare-and-swap operations.
- Add direct real-filesystem tests for durable retries, scope conflicts, encrypted operands, definition-bound refusals, restart-safe response consumption, lease migration, and journal corruption boundaries.

## Outcome

Implementation is review-ready and remains open and uncommitted pending independent review. The completed conflict-scope migration is coherent across the canonical application model, repository protocol, durable path identity, evidence, journal exact-live binding, and supervisor. No duplicate lease, hashing, secure-storage, or interaction authority was introduced.

Focused verification completed:

- `uv run pytest -q -m integration src/cadrumo/application/operations/tests/test_supervisor.py --disable-warnings --maxfail=1` -> 8 passed in 5.85s.
- `uv run pytest -q -m "unit or integration" src/cadrumo/application/operations/tests src/cadrumo/adapters/persistence/operations/tests --disable-warnings --maxfail=1` -> 193 passed in 12.47s.
- `uv run ruff check src/cadrumo/application/operations src/cadrumo/adapters/persistence/operations` -> all checks passed.
- `uv run ruff format --check src/cadrumo/application/operations src/cadrumo/adapters/persistence/operations` -> 32 files already formatted.
- `uv run basedpyright src/cadrumo/application/operations src/cadrumo/adapters/persistence/operations` -> 0 errors, 0 warnings, 0 notes.
- `git diff --check -- src/cadrumo/application/operations src/cadrumo/adapters/persistence/operations .vault/exec/2026-08-11-tui-architecture/2026-08-11-tui-architecture-W02-P05-S22.md` -> clean.

## Notes

Live RAG code search identified `_executor.py`, `_models.py`, `_journal.py`, `_capabilities.py`, and the persistence journal as the canonical implementation cluster. Live vault search returned the binding plan and the governing TUI architecture ADR/research. Targeted `rg` confirmed no substitutable custody, lease, idempotency, or interaction implementation; secure-object storage is reused rather than redeclared. The code index reported missing sections, so absence conclusions were paired with targeted repository search.

The focused supervisor tests exposed and drove two canonical corrections: event-free state transitions must preserve the cursor, and provisional interaction events must satisfy the positive sequence contract before the supervisor assigns their durable sequence. A safe `operation.started` notice anchors the first journal history revision.
