---
step_id: "S16"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W01.P01.S16

**Status**: closed

## What was done

Extended `src/aeat/adapters/outbound/storage/test_local.py` with three real-behavior tests:

- `test_storage_corruption_error_is_registered_in_error_registry` — asserts `INTEGRITY_OUTBOUND_STORAGE_CORRUPTION` is present in `ERROR_REGISTRY`.
- `test_storage_corruption_error_round_trips_through_build_error_envelope` — constructs a `StorageCorruptionError`, calls `build_error_envelope`, asserts code, retryable, and context.
- `test_get_raises_storage_corruption_error_when_sidecar_byte_length_is_wrong_type` — writes a real object to `tmp_path`, corrupts the sidecar's `byte_length` field to a `list`, and asserts `provider.get()` raises `StorageCorruptionError`. No mocks, no stubs.

All 20 tests pass (17 existing + 3 new).

## Files touched

- `src/aeat/adapters/outbound/storage/test_local.py` — three new tests, import of `StorageCorruptionError`, `ERROR_REGISTRY`, `build_error_envelope`

## Commit

`1fc165266`
