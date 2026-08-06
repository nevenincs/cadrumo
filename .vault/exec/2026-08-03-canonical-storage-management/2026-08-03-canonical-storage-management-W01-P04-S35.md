---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:42c5ee55ff6b0620b2aa3d0259b2add0fd6fe53622ebbe64c1945ca35892832d'
step_id: 'S35'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Rewrite the observability run-directory byte total as a caller of the shared helper in tolerant mode, gated by the existing size-bound prune tests

## Scope

- `src/cadrumo/core/observability/_store.py`

## Description

- Rewrite the observability run-directory byte total as a caller of `directory_byte_total` in tolerant mode.

## Outcome

Landed in commit `095bdc4ca2`.

## Notes

Same premature-checkbox / broken-HEAD history as S34; see that record.
