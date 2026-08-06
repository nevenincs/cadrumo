---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:27eaa1e1a7ac37fc6b59a51153dfd44759d3c9b7516e345fdcce99485492c828'
step_id: 'S07'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Export StorageCategory, StorageLocation, STORAGE_TAXONOMY, and the axis enums from the core package facade using the existing deferred-attribute pattern, gated by an import test from the package top level

## Scope

- `src/cadrumo/core/__init__.py`

## Description

- Export `StorageCategory`, `StorageLocation`, `STORAGE_TAXONOMY`, and the axis enums from the core package facade.

## Outcome

Landed in commit `08c61859c0` via eager `from ._storage_taxonomy import (...)` in `core/__init__.py` plus `__all__` entries.

## Notes

The Step text says "using the existing deferred-attribute pattern" (the lazy `__getattr__`/PEP 562 pattern `core/__init__.py` uses for symbols like `BindingSourceKind`). The landed code is NOT lazy — it's an eager top-level import. This is arguably the correct choice under `service-imports-via-top-level-reexports` (eager by default, lazy only where the package already uses it or a cycle risk demands it), but the Step's own wording misdescribes the mechanism actually used. Recorded for honesty rather than silently matched.
