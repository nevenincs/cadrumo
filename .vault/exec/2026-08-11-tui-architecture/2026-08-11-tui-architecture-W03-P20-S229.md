---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:799b8fd78627881c9cab9b3a5a0e0df0cc53d8f10252f2f9c84600a35340fc45'
step_id: 'S229'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Retain record_design as public only for locally defined contract symbols and direct-import every borrowed owner

## Scope

- `src/cadrumo/domain/calculations/registry/record_design.py`

## Changes

- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_keep_public_family.py -n0` -> `pass`

## Notes

No source change was needed: the hard move from `src/cadrumo/domain/calculations/registry/_record_design.py` already
landed and the private module is gone. What was missing was a gate holding it
there, which `test_keep_public_family.py` now does per row - the retired path
must be absent AND unimportable, so a reintroduced private module reds this
row specifically rather than passing for being merely unused.

The surviving owner is asserted from the row's terminal destinations rather
than its `new_path`, because a family that moved out of the registry entirely
leaves a `new_path` nothing occupies.

## Correction

This record closed the row on the hard move alone. The row also asks that the
module stay public only for what it locally defines, and it did not: the export
list was still mostly borrowed names. Corrected in a later pass; the export list
now holds only locally defined symbols. See the narrow-step-closes audit.
