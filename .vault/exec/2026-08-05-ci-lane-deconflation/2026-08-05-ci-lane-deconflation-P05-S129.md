---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:83a11ad188679e72aa477b92dd7985134f3e899c96c1a91385b7415a17451869'
step_id: 'S129'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# `ci-lane-deconflation` execution: `P05.S129`

## Scope

- [ ] `P05.S129` - Refactor the size-budget subjects in secure_objects.py into cohesive siblings without raising any threshold.; `src/cadrumo/adapters/persistence/storage/sql/secure_objects.py`.

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/sql/secure_objects.py`
- `A` `src/cadrumo/adapters/persistence/storage/sql/_secure_object_writes.py`
- `M` `src/cadrumo/adapters/persistence/storage/sql/__init__.py`
- `M` `src/cadrumo/adapters/persistence/storage/sql/tests/_secure_objects_support.py`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/adapters/persistence/storage/sql/tests` -> `pass`

## Notes

- `uv run --no-sync pytest -q src/cadrumo/adapters/persistence/storage/sql/tests` exited 0 with `169 passed, 2 warnings in 7.25s`; direct ownership proof exited 0 and confirmed public writes resolve from `_secure_object_writes.py` while `load` remains in `secure_objects.py`.
- `uv run --no-sync python -m dev.audit.size_budget` exited 1 with 87 remaining whole-tree findings (64 module overages, 22 callable overages, and this target's stale `1617` pin at `1191` lines). `P05.S227` owns the final baseline-only regeneration; no baseline entry was changed here.
