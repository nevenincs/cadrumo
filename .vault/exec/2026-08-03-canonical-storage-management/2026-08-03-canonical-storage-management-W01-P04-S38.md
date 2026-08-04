---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:0140fc4a3b8b439e14cb218b14fdebde01f1426c5b2ce64fc832a96828b4b57a'
step_id: 'S38'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Rewrite the run-trace prune to delegate the survivor decision to the shared selector while keeping its own rmtree and newest-directory-never-size-pruned rule, gated by the existing prune suite

## Scope

- `src/cadrumo/core/observability/_store.py`

## Description

- Rewrite the run-trace prune to delegate the survivor decision to `select_filesystem_retention_survivors`, keeping its own `rmtree` and its newest-directory-never-size-pruned rule.

## Outcome

Landed in commit `095bdc4ca2`.

## Notes

Same premature-checkbox / broken-HEAD history as S37; see that record.
