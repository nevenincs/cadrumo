---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-17'
step_id: 'S07'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Add fingerprint-count eviction for accumulated registry cache pickles

## Scope

- `src/cadrumo/domain/calculations/registry/_loader.py`

## Description

- Add a `cadrumo_registry_disk_cache_max_entries` Settings field (default 8, ge=1) as the eviction ceiling, alongside the registry disk-cache dir field.
- Add a `registry_disk_cache_max_entries()` accessor in `_loader_cache.py` reading that setting, mirroring the `registry_disk_cache_dir` / `registry_disk_cache_enabled` policy accessors.
- Add `_evict_stale_registry_pickles` in `_loader.py`: after a successful pickle write, keep the newest N `cadrumo_registry_*.pkl` files by mtime and unlink the older excess. Fully best-effort - enumerate failures, a file that vanished mid-scan, or an unlink error are logged and swallowed, never raised, so eviction cannot crash a load.
- Add a real-behavior test covering keep-newest/prune-oldest by mtime, glob scoping (unrelated and legacy-named files untouched), the settings accessor, and the missing-directory no-op.
- Refresh the now-stale registry-cache-dir env description and add the new field to `env/.env.example`; regenerate the env-overrides reference.

## Outcome

Registry disk-cache pickles are now bounded per cache directory. Gates: the eviction real-behavior suite, the settings/env-parity suite, the env-reference freshness gate, and the whole-table derivation test all pass; ruff clean; collection clean.

## Notes

The eviction ceiling lives as a central Settings field per the schema-central-config discipline rather than a magic literal in the loader. N=8 is a small, operator-tunable default that covers recent registry re-compiles and rollbacks while bounding disk. The pre-existing peer-owned registry-DATA failures (Modelo 210 / Modelo 100 grounding, normative corpus inventory) triaged under S05 are unchanged and unrelated to this eviction change.
