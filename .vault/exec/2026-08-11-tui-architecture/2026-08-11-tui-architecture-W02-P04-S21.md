---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:4e7ec91665282ef61ed18841b710675c5816c95839d4ae3f5b255d602ba01c89'
step_id: 'S21'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Prove atomic snapshot and event commits, monotonic cursors, idempotent replay, lease conflicts, takeover, and credential-free persistence

## Scope

- `src/cadrumo/adapters/persistence/operations/tests`

## Description

- Exercise the public persistence and application-operation facades against real filesystem roots and fresh child processes.
- Commit complete snapshot-plus-event transitions, restart the repository, and replay deterministic exclusive cursor pages.
- Prove exact live-owner enforcement through conflict, renewal, expiry, takeover, release, and byte-preserving refusal paths.
- Race durable lease and snapshot compare-and-swap transitions without mocks, then inspect the winning persisted records and staging-residue boundary.
- Refuse a linked journal root before it can redirect durable operation bytes.

## Outcome

- Added `test_persistence_integration.py` with four integration tests covering atomic history, monotonic replay, credential-free raw records, restart loading, current-owner enforcement, lease lifecycle, concurrent takeover and journal-CAS races, storage permissions where enforceable, containment, linked-root refusal, and temporary-file cleanup.
- Used only the public persistence-adapter and application-operation package facades.
- Strengthened the raw credential-free proof over the complete journal document: the exact root shape is inspected, the request digest remains exactly once, and the supplied lease owner ID and token are absent from snapshot and full history bytes.

## Verification

- `uv run pytest -q -n 0 -m integration src/cadrumo/adapters/persistence/operations/tests/test_persistence_integration.py` - 4 passed in 5.39s after the credential-free proof remediation.
- `uv run pytest -q -n 0 -m "unit or integration" src/cadrumo/adapters/persistence/operations/tests` - 21 passed in 10.52s after the remediation.
- `uv run ruff check src/cadrumo/adapters/persistence/operations/tests/test_persistence_integration.py` - passed.
- `uv run ruff format --check src/cadrumo/adapters/persistence/operations/tests/test_persistence_integration.py` - already formatted.
- `uv run basedpyright src/cadrumo/adapters/persistence/operations/tests/test_persistence_integration.py` - 0 errors, 0 warnings, 0 notes.
- `uvx vaultspec-core vault check all` - structure, frontmatter, links, placeholders, and the new execution record passed; the shared vault retains pre-existing advisory warnings outside S21 ownership.

## Notes

- One intermediate whole-package rerun briefly failed during shared registry edits with `NameError: _collect_registry_tree_fingerprints is not defined` from `domain/calculations/registry/_loader.py`. No S21 source was altered. A clean fresh S21 rerun and a sequential 21-test persistence package run subsequently passed.
- Leave `W02.P04.S21` unchecked and all S21 changes uncommitted for independent review.

