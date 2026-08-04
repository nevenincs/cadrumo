---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:b7792dbae6d1b3c523ababd25902f95067358cff041ac0d9030186b980c9b30e'
step_id: 'S03'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Declare StorageCategory as a StrEnum naming every application-chosen location identified by scope and name together, gated by a test asserting the duplicated blobs and audit names resolve to distinct members

## Scope

- `src/cadrumo/core/_storage_taxonomy.py`

## Description

- Declare `StorageCategory` as a StrEnum naming every application-chosen location, with the duplicated `blobs`/`audit` names (ADR R13) resolving to distinct members by scope.

## Outcome

Landed in commit `08c61859c0`. Gated by `test_the_duplicated_names_resolve_to_distinct_members` (`BLOBS` ≠ `BUCKET_BLOBS`, `AUDIT` ≠ `BUCKET_AUDIT`, same subpath, different `StorageScope`).

## Notes
