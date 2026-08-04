---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:ebbb0712ff09070b247e9f2f98f1297754a4e57e357c3ce9c0b004702cc698ae'
step_id: 'S15'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Route the settings-cache pointer fingerprint's independent root read through the taxonomy resolver, keeping the deferred submodule-qualified pointer import, gated by a test asserting a profile switch invalidates the cached settings

## Scope

- `src/cadrumo/core/config.py`

## Description

- Route the settings-cache pointer fingerprint's independent root read through the taxonomy resolver, keeping the deferred submodule-qualified pointer import.

## Outcome

Landed in commit `ceaee35e78`. `_active_profile_pointer_fingerprint` resolves the pointer filename via `storage_location(StorageCategory.ACTIVE_PROFILE_POINTER).relative_path()`, importing `_storage_taxonomy` deferred and submodule-qualified inside the function body; the root read itself stays a direct `os.environ.get(...)` read per R19, unchanged, since it must answer "which pointer would the next construction see" before Settings exists. A follow-on commit `b8d8875cdf` further hardens the pinning test.

## Notes
