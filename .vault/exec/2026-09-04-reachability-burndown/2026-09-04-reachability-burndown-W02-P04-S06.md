---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:692867daa8b0ef9479bc7ad54bb9a3940fdf559dfc433b3113c0cfbff083d204'
step_id: 'S06'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
