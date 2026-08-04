---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:a05275dd8409a63e1ffcaddf03784713f3ba5aeecadbba138d88b7054099351b'
step_id: 'S41'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Rewrite the stale registry pickle eviction to delegate the survivor decision to the shared selector, gated by the existing compiled-cache eviction tests

## Scope

- `src/cadrumo/domain/calculations/registry/_compiled_cache.py`

## Description

- Rewrite the stale registry pickle eviction to delegate to `select_filesystem_retention_survivors`.

## Outcome

Landed in commit `095bdc4ca2`.

## Notes

Same premature-checkbox / broken-HEAD history as S37; see that record.
