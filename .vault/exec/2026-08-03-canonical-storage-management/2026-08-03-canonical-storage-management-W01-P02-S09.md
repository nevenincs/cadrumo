---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:1fbd16f2192e1aec9a07e17aaf3c82374ee3e82f7f8e02b0d0065313d12576df'
step_id: 'S09'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add the bucket-scoped and keystore-scoped accessor variant taking the bucket identifier, gated by a test asserting a root-scoped member passed to it refuses rather than silently resolving

## Scope

- `src/cadrumo/core/_storage_taxonomy.py`

## Description

- Add `bucket_scoped_storage_path` taking the bucket identifier for per-bucket members.

## Outcome

Landed in commit `08c61859c0`. Gated by `test_storage_path_refuses_a_scoped_member_rather_than_resolving_it` and `test_the_scoped_accessor_refuses_a_root_member_and_a_blank_bucket`.

## Notes
