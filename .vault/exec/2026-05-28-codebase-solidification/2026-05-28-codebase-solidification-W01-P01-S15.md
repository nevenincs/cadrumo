---
step_id: "S15"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W01.P01.S15

**Status**: closed

## What was done

Introduced `StorageCorruptionError(CoreError)` in `src/aeat/adapters/outbound/storage/_errors.py`.

Replaced both `TypeError` raises at the sidecar `byte_length` validation boundary in `_local.py` (inside `get()` at line 271 and `iter_objects()` at line 331) with `raise StorageCorruptionError(...)`. Both sites share identical corruption semantics.

Added `get_logger(__name__)` to `_local.py` and emitted an `.error()` log entry before each raise.

Registered the new error under code `INTEGRITY_OUTBOUND_STORAGE_CORRUPTION` (category `INTEGRITY`, `retryable=False`) in `src/aeat/core/errors/registry/_adapters.py`.

Scaffolded locale key `errors.integrity.integrity_outbound_storage_corruption` via `python -m aeat.locales scaffold` and set English/Spanish translations via `python -m aeat.locales set`.

Exported `StorageCorruptionError` from the storage package `__init__.py`.

## Files touched

- `src/aeat/adapters/outbound/storage/_errors.py` — added `StorageCorruptionError(CoreError)`
- `src/aeat/adapters/outbound/storage/_local.py` — import + logger + two `TypeError` → `StorageCorruptionError` replacements
- `src/aeat/adapters/outbound/storage/__init__.py` — exported `StorageCorruptionError`
- `src/aeat/core/errors/registry/_adapters.py` — registry entry for `StorageCorruptionError`
- `src/aeat/locales/en.yml`, `es.yml` (+ others via scaffold) — new locale key

## Commit

`1fc165266`
