---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:c30d88be693d953283f8f3aa9d7f75d953014f0b4d041c1c601123f8d7302444'
step_id: 'S92'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Sweep the second stale-pin class the path sweep could not see: gates naming their canonical module by bare basename, distinguishing those from assertions that a retired module is absent

## Scope

- `src/cadrumo/`
- `dev/`

## Changes

- `M` `src/cadrumo/application/modelo/tests/test_workspace_manifest.py`
- `M` `src/cadrumo/application/user_profile/tests/test_hold_decision_has_one_door.py`
- `M` `src/cadrumo/entrypoints/tests/test_operation_composition.py`
- `M` `src/cadrumo/entrypoints/tests/test_google_operation.py`
- `M` `src/cadrumo/tests/test_enum_constant_extraction_inventory.py`
- `M` `src/cadrumo/core/tests/test_external_constants_centralisation_part2.py`
- `M` `dev/tests/test_public_authority_cutover.py`
- `verify:` `pytest <the seven gates> -n 0 -m ""` -> `pass`

## Notes

Four of the thirteen candidates were reverted rather than repointed: they assert
that the RETIRED private module is absent, so repointing them inverted the test
into asserting the live module does not exist. One failed and said so, which is
how the class was found. A `_x.py` literal means one of two opposite things.
