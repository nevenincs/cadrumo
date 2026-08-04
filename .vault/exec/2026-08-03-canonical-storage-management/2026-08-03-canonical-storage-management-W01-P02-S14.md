---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:411e7503569f3d1a07f12d7b61fef59395680587dc153cc224bbdf8f7aeb899b'
step_id: 'S14'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Rewrite the override-settings root-change pop-and-rebuild loop against the taxonomy key space, gated by a test asserting a root override re-derives every non-overridden category under the new root

## Scope

- `src/cadrumo/core/config.py`

## Description

- Rewrite the override-settings root-change pop-and-rebuild loop against the taxonomy key space (`ROOT_DERIVED_STORAGE_FIELDS` replacing `_STATE_ROOT_DERIVED_DIRS`).

## Outcome

Landed in commit `ceaee35e78`. Gated by the existing root-override-re-derives-every-non-overridden-category test.

## Notes
