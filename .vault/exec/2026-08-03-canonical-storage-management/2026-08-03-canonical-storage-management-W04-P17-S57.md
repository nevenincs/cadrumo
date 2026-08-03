---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:78109f75da519047d4abc6de161487c4968503e57b70409924c06f161c358876'
step_id: 'S57'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Register the config storage noun-group and its five verbs as a lifecycle-operations-only entry in the CRUD catalogue, gated by the catalogue conformance suite resolving the new path

## Scope

- `src/cadrumo/entrypoints/cli/_config/_storage_cli.py`

## Description

- Register `config storage` as a `LIFECYCLE_OPERATIONS_ONLY` noun-group with its five verbs (`list`, `show`, `check`, `init`, `reclaim`) in the CRUD catalogue.

## Outcome

Landed in commit `ecd388183f`, an ancestor of `bb18425074`; checkbox corrected here.

## Notes
