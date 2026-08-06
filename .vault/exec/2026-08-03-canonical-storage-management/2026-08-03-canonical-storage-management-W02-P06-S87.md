---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:0a356605d18434d99f3fd66a8621b993d4ad20d4cdabb0fc6c72baecb19460c9'
step_id: 'S87'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Declare the local storage provider's per-namespace fan-out beneath BUCKET_BLOBS as a governed segment, since the provider's root resolves correctly through bucket_paths but the namespace subdirectory it creates beneath that root is an ungoverned literal

## Scope

- `src/cadrumo/adapters/outbound/storage/_local.py`

## Description

- Declare the local storage provider's per-namespace fan-out beneath BUCKET_BLOBS as a governed shape.

## Outcome

Landed in the same commit as S86, `3a6ce7475d`. `local_provider_object` (`grammar="<root>/buckets/<bucket_id>/blobs/<namespace>/<hmac_prefix>--<label>.bin"`) and `local_provider_object_sidecar` (`.meta.json`) declare the shape via `StoragePathDefinition`, with `namespace` and `hmac_prefix`/`label` bounded only as "not a path separator" per the grammar-assertion helper (`tests/_storage_path_grammar.py`), since they are free-form application-chosen identifiers rather than hash-shaped. Gated by `adapters/outbound/storage/tests/test_local_provider_object_shape_conformance.py`.

## Notes

Found landed while backfilling S86 — not called out individually in the honesty review or the coordinator's relay of it, but covered by the same commit and mechanism. Verified independently before marking done.
