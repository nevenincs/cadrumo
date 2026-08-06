---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:a7afe0b603116865cd2494cae2b69e78e5d4f2631b7a6f42fa8f9808306286e5'
step_id: 'S91'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Declare the amendments and amendment-results nested segments under the submissions category as governed members, preserving the module's own HKDF-context separation requirement that the two must stay distinct rather than collapsing them, and declare the sibling manifests segment under financial slash attachments found on the fuller enumeration in the same module

## Scope

- `src/cadrumo/adapters/persistence/storage/_rotation.py`

## Description

## Outcome

Landed by a peer lane, confirmed at pinned HEAD `b6287cd8f5`. `StorageCategory` carries `SUBMISSIONS_AMENDMENT_RESULTS`, `SUBMISSIONS_AMENDMENTS`, and `ATTACHMENTS_MANIFESTS` as three distinct members, preserving the module's own HKDF-context separation between amendments and amendment-results rather than collapsing them. `adapters/persistence/storage/_rotation.py` resolves all three through `storage_location(StorageCategory....).subpath` rather than a literal, confirmed by direct read of the module at the pinned SHA (lines 68-72, 443, 472, 476).

## Notes
