---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:f27b6dd4344b69f2f27d2e6d3c263773335aa5665eed8d61a8944ad60302f277'
step_id: 'S118'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Implement the observation-read port over one locked journal-record read so snapshot, history page, progress checkpoint, replay status, and restart cursor share one authoritative anchor under interleaved transitions

## Scope

- `src/cadrumo/adapters/persistence/operations/_journal.py`
- `src/cadrumo/application/operations/_journal.py`
- `src/cadrumo/application/operations/__init__.py`
- `src/cadrumo/adapters/persistence/operations/tests/test_journal.py`

## Description

- Implemented the `OperationObservationReader` port on the filesystem operation-journal adapter.
- Derived the snapshot, bounded replay page, authoritative cursor, and complete progress-fold input from one parsed `OperationJournalRecord` while the canonical journal lock is held.
- Extracted the retained-history page builder from `read_after` so replay and atomic observation use one canonical record-to-page implementation.
- Added narrow application-owned errors for an absent operation and a cursor beyond the locked anchor, leaving corrupt persistence bytes as adapter errors.
- Validated an existing journal root before lock-sidecar access and refused absent or redirected roots without filesystem mutation.
- Proved atomicity with real multiprocessing, entry into the production lock context, a writer transition, and replay shapes that distinguish the two durable generations.

## Outcome

- `OperationJournalRepository` now provides the sole concrete observation-reader implementation.
- No frontend or application projection joins separate snapshot and replay reads.
- The observation materialization carries the full retained progress suffix independently of the bounded replay page.
- Public operation consumers can distinguish missing-operation and cursor-ahead port states without importing persistence errors.

## Verification

- `uv run --no-sync pytest -q src/cadrumo/adapters/persistence/operations/tests/test_journal.py` â€” 20 passed.
- `uv run --no-sync pytest -q src/cadrumo/application/operations/tests/test_journal.py src/cadrumo/application/operations/tests/test_facade.py src/cadrumo/adapters/persistence/operations/tests/test_journal.py` â€” 38 passed.
- `uv run --no-sync ruff check` over changed application and persistence modules â€” passed.
- `uv run --no-sync ty check` over changed application and persistence modules â€” passed.
- Post-edit semantic and exact discovery converged on one concrete observation reader, one record-to-page helper, and no snapshot/replay join.
- Independent review initially found root-sidecar mutation and weak atomicity witnesses; both were corrected and the remediation re-review approved with no remaining findings.

## Notes

- The broader operation-platform suite has one known unrelated persistence-facade export-inventory failure caused by concurrent secure-reference namespace work. The focused S118 tests and all touched-module static checks pass.
- The plan step remains open for the parent executor to sequence its closure with the surrounding operation-platform work.
