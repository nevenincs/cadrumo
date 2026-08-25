---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:5306633f51bc5bd97ffb8bb32c096dbd6e11fd80557a24efe44bf1fb67c7a428'
step_id: 'S119'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Consolidate duplicate secure-object ephemeral repository test helpers behind the canonical shared support owner while preserving each caller's database-path and key-lifecycle contract

## Scope

- `src/cadrumo/adapters/persistence/storage/sql/tests/_secure_objects_support.py`
- `src/cadrumo/adapters/persistence/storage/sql/tests/test_secure_object_write_batching.py`
- `src/cadrumo/adapters/persistence/storage/sql/tests/test_secure_objects_part2.py`
- `dev/quality/tests/test_helper_body_census.py`

## Description

- Move the filename and explicit-database-path ephemeral repository test helpers into one canonical support module.
- Preserve fresh key-provider ownership, engine disposal, and each consumer's return-tuple contract.
- Remove local helper definitions and pin the exact definitions and direct imports through the helper-body census.

## Outcome

Commit `e8475e8289` makes `_secure_objects_support.py` the sole definition owner for `_ephemeral_secure_repo` and `_ephemeral_secure_repo_at`. The batching and part-two suites import those helpers directly; no compatibility wrapper or duplicate body remains.

The focused affected and helper-census suite passes 40 tests. Ruff, format, and diff checks pass, and independent review found no remaining lifecycle or ownership residue.

## Notes

- Remaining direct `EphemeralMasterKeyProvider` uses in part two exercise intentional seed/reopen lifecycles and are not helper redeclarations.
