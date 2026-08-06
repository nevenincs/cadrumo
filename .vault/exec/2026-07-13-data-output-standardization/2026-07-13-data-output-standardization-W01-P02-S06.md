---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-17'
body_hash: 'sha256:45cddd0cc6d2af3a3564e5eefecf9fdee0dab93653faf816d1c1366adf45686a'
step_id: 'S06'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Move the registry disk-cache production default under the cache root, rename the pickle stem to cadrumo, preserve xdist fingerprint sharing

## Scope

- `src/cadrumo/domain/calculations/registry/_loader_cache.py`

## Description

- Change `registry_disk_cache_dir()` so the production (non-pytest) default derives `<cadrumo_local_storage_root>/cache/registry` instead of the shared OS temp directory, keeping the explicit `CADRUMO_REGISTRY_DISK_CACHE_DIR` override as the highest-precedence path.
- Retain the host-shared OS temp directory ONLY under pytest with no override, so the immutable bundled-root pickle stays shared across xdist workers (each worker gets a per-pid storage root, so deriving from it would give every worker a private cache and defeat the single-compile sharing).
- Extract the pytest-detection predicate into a `_running_under_pytest()` helper reused by `registry_disk_cache_enabled` and the new dir resolution.
- Rename the disk-pickle stem `aeat_registry_` to `cadrumo_registry_` in `_loader.py`, and mkdir the derived cache directory best-effort before the write so a cold first run has a parent (falling through to recompute-and-skip on any failure, never crashing the load).
- Sweep the renamed pickle-stem glob and docstrings in the loader-cache isolation test and the package conftest to keep them green with the rename (relocation-atomicity: the rename and its direct name consumers land together).

## Outcome

The registry disk pickle no longer defaults into the world-shared OS temp directory in production; it derives one per-user location under the storage root, while the pytest cross-worker sharing semantics are preserved unchanged. Gates: the loader-cache isolation suite is 10 passed under sequential (`-n 0`) re-run, including the two cross-process/cross-session sharing proofs (now keyed to the renamed stem); ruff clean; collection clean.

## Notes

The registry disk cache dir field (`cadrumo_registry_disk_cache_dir`) already existed as the override; this Step changed only the fallback, so no new Settings field was needed here. The full registry suite still carries the pre-existing peer-owned registry-DATA failures triaged under S05 (Modelo 210 / Modelo 100 grounding, normative corpus inventory) - unaffected by and unrelated to this cache-location change.
