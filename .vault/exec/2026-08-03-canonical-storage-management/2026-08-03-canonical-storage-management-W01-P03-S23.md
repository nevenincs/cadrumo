---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:7212ee0f11aa35a53d408935949b812b93e4dceaeb1ec0e3e9a95c5806d14e97'
step_id: 'S23'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Delete the inline buckets and db literals in the storage-route classifier's parts matching and read the taxonomy instead, gated by the route-classification suite

## Scope

- `src/cadrumo/core/_config_storage_route.py`

## Description

- Delete the inline `buckets` and `db` literals in the storage-route classifier's parts matching and read the taxonomy instead.

## Outcome

Landed in commit `ceaee35e78` ("derive settings paths and the override rebuild from the taxonomy"). Verified independently at committed HEAD: no bare `"buckets"` or `"db"` string literal remains in `core/_config_storage_route.py`.

## Notes
