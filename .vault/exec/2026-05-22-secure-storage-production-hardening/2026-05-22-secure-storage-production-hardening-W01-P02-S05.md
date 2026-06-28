---
tags: ["#exec", "#secure-storage-production-hardening"]
date: "2026-05-22"
modified: '2026-05-22'
step_id: "S05"
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# `secure-storage-production-hardening` `W01.P02.S05`

Introduced bucket-scoped DEK activation while preserving legacy bucket readability.

- Modified: `src/aeat/adapters/persistence/storage/master_key/_master_key.py`
- Modified: `src/aeat/adapters/persistence/storage/master_key/test_master_key.py`

## Description

Provider activation now resolves the active bucket, loads the process master key as KEK, and then unwraps a separated per-bucket DEK from the bucket keystore. Bootstrap activation for a not-yet-registered profile mints a fresh DEK, wraps it with the existing AES-GCM DEK wrapper, and persists it under the separated keystore tree.

Existing registered buckets without a separated DEK document retain the legacy master-key data path instead of receiving a fresh random DEK that would make prior ciphertext unreadable. The unsecured backend also keeps its published deterministic data-key behavior for the current test and throwaway surface; stricter unsecured refusal remains in the later route-guard step.

## Tests

Validated that bootstrap activation persists a distinct bucket DEK, that a second provider instance unwraps the same DEK, and that legacy registered buckets without a DEK document stay readable through the master-key path.
