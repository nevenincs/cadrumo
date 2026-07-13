---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S06'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace data-output-standardization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-07-13-data-output-standardization-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Move the registry disk-cache production default under the cache root, rename the pickle stem to cadrumo, preserve xdist fingerprint sharing and ## Scope

- `src/cadrumo/domain/calculations/registry/_loader_cache.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
