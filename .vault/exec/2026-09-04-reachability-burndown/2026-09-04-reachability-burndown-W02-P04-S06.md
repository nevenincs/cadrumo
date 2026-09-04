---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:e9d1a74e6a47c9559f8b83b7d6503c507d0eaceff22cf830c09f3227f5b25ea0'
step_id: 'S06'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Resolve the operator_surface CRUD catalogue cluster against its conformance-test consumer

## Scope

- `src/cadrumo/application/operator_surface`

## Changes

- `verify:` `uv run --no-sync python -m dev.quality.unreachable_module_ratchet` -> `pass`

## Notes

Already resolved by the corrected remedy Step in the preceding Phase, and recorded here so
the Step is closed by its evidence rather than left open against work that has landed.

The cluster's adjudication is that `crud_contract` and `crud_registry` are design-time
authorities, not code awaiting a caller. `crud_registry` carries the locked CRUD design for
the operator CLI and `crud_contract` the verb vocabulary it instantiates; the reader is
`dev/quality/crud_contract_drift.py`, which checks the shipped Typer subgroups against the
declaration. No entrypoints module uses `CrudVerb`, `CANONICAL_CRUD_VERBS` or
`get_builtin_catalogue`, and that absence is the contract holding rather than a gap.

Both now carry typed `[[intentional]]` dispositions in the module ratchet naming that
reader, and both left the `allowed` backlog, which shrank from 14 to 10.
