---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:2fc4e09854651bc12867b87bf5cf45ed1271afd35f0f50011789e41a6764b651'
step_id: 'S20'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Expose the persistence adapter facade without exporting implementation internals

## Scope

- `src/cadrumo/adapters/persistence/operations/__init__.py`

## Description

- Re-export `OperationJournalRepository` and `OperationLeaseFilesystemRepository` from the package root.
- Declare the exact two-name public surface through `__all__`.
- Keep `OperationLeaseStorage` adapter-local and prove it is absent from the package namespace.
- Add a direct package-facade test using only the public adapter package.

## Outcome

The persistence facade exposes only the concrete journal and owner-lease repositories. It does not promote the shared lease-storage and lock helper, leaving journal-lock composition internal to the two concrete adapters.

Focused verification passed:

- `pytest`: 32 passed across the S18/S19 regression suite and the new facade contract.
- Ruff check and format check: passed.
- Basedpyright: 0 errors, 0 warnings, 0 notes.
- Path-scoped relative-import gate: passed.

## Notes

Fresh code and vault RAG grounding, whole-file adapter reads, exact-symbol confirmation, and the S18/S19 execution and review records all converge on the two-repository facade. The RAG code index reported one unpublished section; the exact-source sweep supplied the required absence evidence.

This record is scaffolded and the implementation remains open for independent review. The plan step is intentionally unchecked and no commit was created.
