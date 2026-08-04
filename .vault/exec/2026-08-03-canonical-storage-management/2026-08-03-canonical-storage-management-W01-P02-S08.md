---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:5654147a6f9d2b5174e5f3544eb25808d87793fd4baeb7068905108357bb6811'
step_id: 'S08'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add storage_path returning the resolved absolute path for a root-scoped category, gated by a test asserting an absolute per-field override passes through unchanged with no containment rewrite

## Scope

- `src/cadrumo/core/_storage_taxonomy.py`

## Description

- Add `storage_path` returning the resolved absolute path for a root-scoped category.

## Outcome

Landed in commit `08c61859c0`. Gated by `test_storage_path_reads_the_member_field_so_an_override_wins` (an absolute per-field override passes through unchanged, no containment rewrite).

## Notes
