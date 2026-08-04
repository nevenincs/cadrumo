---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:c322a44b542bf623dba68d97094a879349e972104a98cc2ab8050e0f70a757cd'
step_id: 'S53'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Re-point the observability run-trace directory read onto the accessor, gated by the existing run-store suite

## Scope

- `src/cadrumo/core/observability/_store.py`

## Description

## Outcome

Landed in `06eb40877b`, confirmed at HEAD. `src/cadrumo/core/observability/_store.py:127` returns `storage_path(StorageCategory.RUNS, settings=settings)` rather than reading `cadrumo_runs_dir` directly. Gated by the existing `observability/tests/` run-store suite.

## Notes
