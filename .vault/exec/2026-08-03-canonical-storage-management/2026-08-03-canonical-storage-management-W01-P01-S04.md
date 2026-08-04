---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:566843b91ad2d3494a591df6b502e5bf39188e1df4aab4dbdc4a0ad13cf2ba4f'
step_id: 'S04'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Declare StorageLocation as a frozen strict pydantic model carrying subpath, node kind, scope, override policy, lifecycle, grouping, and fingerprint participation, gated by a test asserting extra fields are forbidden and mutation raises

## Scope

- `src/cadrumo/core/_storage_taxonomy.py`

## Description

- Declare `StorageLocation` as a frozen strict pydantic model carrying subpath, node kind, scope, override policy, lifecycle, grouping, and fingerprint participation.

## Outcome

Landed in commit `08c61859c0`. Gated by `test_a_declaration_forbids_extra_fields_and_refuses_mutation`.

## Notes
