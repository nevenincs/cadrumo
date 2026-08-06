---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:7db558e8ed5d5594bbe7151327c59ea35f65217282c4d545f1734abd1877bb96'
step_id: 'S22'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Delete the inline buckets and db literals in the bucket database path construction and read the taxonomy instead, gated by the route-classification suite

## Scope

- `src/cadrumo/core/config.py`

## Description

- Delete the inline `buckets` and `db` literals in the bucket database path construction and read the taxonomy instead.

## Outcome

Landed in commit `ceaee35e78` ("derive settings paths and the override rebuild from the taxonomy"). Verified independently at committed HEAD: no bare `"buckets"` or `"db"` string literal remains in `core/config.py`'s database-URL construction.

## Notes
