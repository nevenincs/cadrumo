---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:7ae373972590252688c6f6c39ceab84ecb6c28b2a34fb03ee2f776f4a039bee1'
step_id: 'S236'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Retain schema local definitions, migrate borrowed symbols to their canonical owners, and remove borrowed bindings

## Scope

- `src/cadrumo/domain/calculations/registry/schema.py`
- `existing schema_*`
- `export_semantics`
- `and export_value_policy owners`

## Changes

- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_keep_public_family.py -n0` -> `pass`

## Notes

No source change was needed: the hard move from `src/cadrumo/domain/calculations/registry/_schema.py` already
landed and the private module is gone. What was missing was a gate holding it
there, which `test_keep_public_family.py` now does per row - the retired path
must be absent AND unimportable, so a reintroduced private module reds this
row specifically rather than passing for being merely unused.

The surviving owner is asserted from the row's terminal destinations rather
than its `new_path`, because a family that moved out of the registry entirely
leaves a `new_path` nothing occupies.
