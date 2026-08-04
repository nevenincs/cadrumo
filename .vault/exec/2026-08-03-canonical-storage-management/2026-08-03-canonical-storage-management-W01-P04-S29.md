---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:41b3feb54526e273f39d98e4d38390693397e8b207e7985ae7ec2771a6787fa3'
step_id: 'S29'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Rewrite bucket_dek_path as a one-line caller of keystore_sidecar_path, gated by the existing master-key custody suite

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_master_key_bucket_dek.py`

## Description

## Outcome

Landed in `4425e24ecf`, confirmed at HEAD. `bucket_dek_path` in `src/cadrumo/adapters/persistence/storage/master_key/_master_key_bucket_dek.py:27-32` is a one-line caller of `keystore_sidecar_path`, gated by the existing master-key custody suite. Note: the filename constant is still imported from `.._namespace_registry` (line 29) — the retired re-export bridge `S113` targets; not a defect in this Step, since `S27`'s new `keystore_sidecar_path` call itself is clean, but worth knowing this call site is one of the ten still reaching the bridge.

## Notes
