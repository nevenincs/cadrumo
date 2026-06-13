---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S149'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s149-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S149`

Closed `AFR-047` for the storage package public facade.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/__init__.py` against the `runtime` and `master-key` scanner signals.
- Kept the package root as the canonical import boundary for runtime readiness, active bucket session, master-key provider, and secure-object hierarchy registry symbols.
- Documented the runtime/master-key session boundary and namespace registry groups in the package docstring.
- Added a real public-surface guard proving critical runtime, master-key, and namespace symbols remain exported through `aeat.adapters.persistence.storage`.
- Closed `W12.P26.S149` through `vaultspec-core vault plan step check` and aligned the AFR register row to `closed`.

## Outcome

`AFR-047` is closed as `runtime-default`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_smoke.py src/aeat/adapters/persistence/storage/test_namespace_registry.py -k "public_surface or runtime_master_key or secure_object_logical_path"`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/test_smoke.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `git diff --check -- src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/test_smoke.py`

## Notes

This is a facade hardening step, not a storage-format migration. The risk addressed is API drift: production callers should not be forced back into private runtime or master-key modules to access storage state.
