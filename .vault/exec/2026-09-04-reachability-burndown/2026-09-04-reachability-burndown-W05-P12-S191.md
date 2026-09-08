---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:5c936c85bf0a2917da3521d22fee75a7389926c250cd596e5c1b24beafb1a18a'
step_id: 'S191'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the test-only declare_prorrata_entry adapter convenience facade and migrate its roundtrip test to the canonical ProrrataRegisterRepository.upsert_entry owner while retaining the live ProrrataRegisterService coordinate validation, secure register persistence, and cross-period calculation consumers.

## Scope

- `Prorrata persistence facade and roundtrip test`
- `canonical application and repository ownership`
- `exact reachability signal`
- `focused gates`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `src/cadrumo/adapters/persistence/profile/prorrata_register.py`
- `M` `src/cadrumo/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/persistence/profile/prorrata_register.py src/cadrumo/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py src/cadrumo/application/prorrata_register/service.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_coverage` -> `fail`

## Notes

- The exact detector reports 337 unused symbols and 18 orphan test modules, down from 338 and 18 before S191; no baseline, threshold, or disposition list changed.
- The combined adapter-and-application run passed the adapter roundtrip tests but has ten peer-owned application-fixture failures requiring official declaration or registry-snapshot provenance. None calls the deleted adapter facade.
