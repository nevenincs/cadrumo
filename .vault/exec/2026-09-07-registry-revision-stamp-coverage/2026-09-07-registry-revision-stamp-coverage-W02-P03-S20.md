---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:02480b587cb1f5a42dc37fdf76209e54844abb4785d4390b0f34aeb66e383b72'
step_id: 'S20'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Require the producing RegistrySnapshotRef on ModeloReconciliationRecord and copy it during reconciliation

## Scope

- `src/cadrumo/application/modelo/reconciliation_records.py`
- `src/cadrumo/application/modelo/reconciliation.py`

## Changes

- `M` `src/cadrumo/application/modelo/reconciliation_records.py`
- `M` `src/cadrumo/application/modelo/reconciliation.py`
