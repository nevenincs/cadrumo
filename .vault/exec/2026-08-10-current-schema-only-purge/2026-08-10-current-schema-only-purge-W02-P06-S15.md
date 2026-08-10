---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:32e1a806f0e132651255f99be2f772f63dff8ca4fb10c17c27bd12608478a546'
step_id: 'S15'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Prove missing and non-current secret-index markers refuse real store operations

## Scope

- `src/cadrumo/adapters/persistence/storage/secret_store/tests/test_secret_index_version_gate.py`

## Description

- Prove an index file omitting the version refuses on reads.
- Prove it refuses on mutations, and that the file's bytes are unchanged
  afterwards.
- Prove the absent-file path still materialises a usable store.
- Keep the existing future-version and restore-the-supported-version coverage.

## Outcome

Landed in `005816f` alongside the production change.

The file already covered a future version refusing reads and refusing mutations
without rewriting. It did not cover omission at all, which is the case the field
default had made unreachable.

The bytes-unchanged assertion on the mutation path is the one carrying real
weight. A refusal that happens after the index has been rewritten is not a
refusal, it is a corruption with an exception attached -- and on a store whose
every mutation rewrites the whole document, that is the specific failure worth
proving against rather than reasoning about.

The absent-file proof is a positive control. Requiring the marker could have
broken create-on-first-access, and a suite of refusal tests would all still pass
while the store had become unusable from a clean state.

## Notes

Real store operations against real files throughout; no mocks and no patched
parser.
