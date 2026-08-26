---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:75e0dc3f293bae1e47ab575804b5a29a7090141cdcc83b06d8839c975369b6e4'
step_id: 'S230'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Hard-move ENCODING_ALIAS_MAP to schema_exports and delete the record_spec surface

## Scope

- `src/cadrumo/domain/calculations/registry/record_spec.py and src/cadrumo/domain/calculations/registry/schema_exports.py`

## Changes

- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_keep_public_family.py -n0` -> `pass`

## Notes

No source change was needed: the hard move from `src/cadrumo/domain/calculations/registry/_record_spec.py` already
landed and the private module is gone. What was missing was a gate holding it
there, which `test_keep_public_family.py` now does per row - the retired path
must be absent AND unimportable, so a reintroduced private module reds this
row specifically rather than passing for being merely unused.

The surviving owner is asserted from the row's terminal destinations rather
than its `new_path`, because a family that moved out of the registry entirely
leaves a `new_path` nothing occupies.
