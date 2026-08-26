---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:6ef9959d7634f395c28162e8c34f5d68e629bea2ec64c1b09d2e3c7d77afdb58'
step_id: 'S232'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Retain relations as public only for locally defined contract symbols and direct-import every borrowed owner

## Scope

- `src/cadrumo/domain/calculations/registry/relations.py`

## Changes

- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_keep_public_family.py -n0` -> `pass`

## Notes

No source change was needed: the hard move from `src/cadrumo/domain/calculations/registry/_relations.py` already
landed and the private module is gone. What was missing was a gate holding it
there, which `test_keep_public_family.py` now does per row - the retired path
must be absent AND unimportable, so a reintroduced private module reds this
row specifically rather than passing for being merely unused.

The surviving owner is asserted from the row's terminal destinations rather
than its `new_path`, because a family that moved out of the registry entirely
leaves a `new_path` nothing occupies.
