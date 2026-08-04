---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:2cc211db81519ded22ed8e123c7287ee4f2dcdad590e9c0e334022c3775b5058'
step_id: 'S30'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Rewrite login_throttle_path as a one-line caller of keystore_sidecar_path, gated by the existing login-throttle suite

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_login_throttle.py`

## Description

## Outcome

Landed in `8f4cb2ee33`, confirmed at HEAD. `login_throttle_path` in `src/cadrumo/adapters/persistence/storage/master_key/_login_throttle.py:104-108` is a one-line caller of `keystore_sidecar_path`, gated by the existing login-throttle suite.

## Notes
