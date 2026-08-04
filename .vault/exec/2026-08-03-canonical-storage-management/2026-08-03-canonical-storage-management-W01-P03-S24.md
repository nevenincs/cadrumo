---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:8efdbb6805db786b63879e2ba06e1cd1227ee6d341ec45a175a962612776634a'
step_id: 'S24'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Re-point the active-profile pointer filename onto its taxonomy member, gated by a test asserting the pointer round-trips through the taxonomy-resolved path

## Scope

- `src/cadrumo/core/_bucket_pointer_io.py`

## Description

- Re-point the active-profile pointer filename onto its taxonomy member, gated by a test asserting the pointer round-trips through the taxonomy-resolved path.

## Outcome

Landed as "fix(core): enroll active-profile pointer path through the storage taxonomy." `pointer_path()` now returns `root / storage_location(StorageCategory.ACTIVE_PROFILE_POINTER).relative_path()` instead of joining a bare `_POINTER_FILENAME` constant. **No exception needed**: the taxonomy module has no runtime import path back to `config.py`, so the pre-existing deferred, submodule-qualified import (kept for the bootstrap-ordering reason `_active_profile_pointer_fingerprint` already documents — this module is read during `Settings()` bootstrap, before `Settings` exists) was sufficient on its own; the bootstrap-cycle guard test passes. Verified directly against committed HEAD.

## Notes

This Step was checked, found genuinely not done on a fresh-context honesty review, unchecked, and is now genuinely done — the third instance of "checked Step, code disagreed" in this campaign (with `S42`, `S54`), and the only one of the three where the checkbox turned out wrong rather than merely unaccountable. Re-verified against committed HEAD rather than trusting the coordinator's relay before checking it again here.
