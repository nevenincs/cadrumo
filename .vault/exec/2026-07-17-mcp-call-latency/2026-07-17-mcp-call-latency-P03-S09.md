---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-19'
step_id: 'S09'
related:
  - "[[2026-07-17-mcp-call-latency-plan]]"
---

# Load the compiled cache when the tree fingerprint matches so warm processes skip the TOML parse, and write the cache after a fresh compile, wired through the loader

## Scope

- `src/cadrumo/domain/calculations/registry/_loader.py`

## Description

- Rewrite `_load_registry_tree_cached` in `_loader.py` to read through `load_compiled_registry_cache` on a fingerprint match (skipping the TOML parse) and write through `store_compiled_registry_cache` after a fresh compile, replacing the inline verbatim-pickle read/write block.
- Relocate the compiled-cache machinery from `_loader.py` into `_compiled_cache.py` as its permanent home: the schema-version marker, the embedded-core-module list, `_compute_loader_code_fingerprint`, `_LOADER_CODE_FINGERPRINT`, `_registry_disk_cache_key`, and `_evict_stale_registry_pickles`; delete the loader's `_read_registry_disk_cache_pickle` (replaced by the integrity-checked read) and its read-attempt constants.
- Update the three consumers of the relocated symbols in the same atomic commit: `test_registry_disk_cache_loader_fingerprint.py` (import from `_compiled_cache`; poison via the framed `_encode_frame`, since a raw verbatim pickle is now refused), `test_registry_cache_eviction.py` (import `_evict_stale_registry_pickles` from `_compiled_cache`), and the core `test_retention_wiring_gate.py` (point the registry prune-call-site row at `_compiled_cache.py`).

## Outcome

Relocated + focused suites pass (33 passed: loader-fingerprint, eviction, compiled-cache module, retention wiring, reviewability, loader-cache isolation). Authority-load path unaffected (29 passed: validation-verdict cache + location + modelo-130 registry). Whole-tree `pytest --collect-only -q src/cadrumo` is clean (12919 tests collected, no import errors) - the loader-to-compiled-cache import edge introduces no cycle (compiled cache imports only `_loader_cache` and `_schema`, never `_loader`). Gates green on all authored files: `ruff check`, `ruff format --check`, `ty check`.

Measured warm delta on the bundled tree (settings-derived cache dir): cold compile 6.5 s versus warm cache load 1.34 s - the 17,276-file TOML parse collapses to a single framed-file read. The warm floor (~1.3 s) is the unpickle of the 20.7 MB compiled set (923 pydantic models); the added SHA-256 integrity digest and structural type-check cost no measurable time. The pre-existing pickle already delivered most of this warm win; S09's net change is the strict-integrity hardening (never a second authority) at zero warm cost.

## Notes

This is the atomic completion of the relocation begun in S08: after this commit the compiled-cache key/fingerprint/eviction logic exists only in `_compiled_cache.py`, with no duplication remaining in `_loader.py`. The relocation moved a retention-classified prune call site, so the core retention-wiring gate's map was updated to name `_compiled_cache.py` - a truthful move, not a loosening. The relocated helpers keep their existing private names so the fingerprint invalidation contract and its test assertions are unchanged.
