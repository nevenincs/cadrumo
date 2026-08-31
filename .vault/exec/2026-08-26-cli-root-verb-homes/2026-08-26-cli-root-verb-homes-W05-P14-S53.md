---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:280fc5a702e12294c6a01edd62e8f2204f4699334dfe5b7c34e55fd7aa8d36f2'
step_id: 'S53'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Repair the three CLI test modules carried as collection exclusions since the close review - the cause was peer-owned but the fix was always in this package

## Scope

- `src/cadrumo/entrypoints/cli/tests/`

## Changes

- `M` `src/cadrumo/entrypoints/cli/tests/test_storage_session_preconditions.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_fast_path_no_state.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_ledger_exception_propagation.py`
- `verify:` `pytest the three modules -p no:randomly -n0` -> `12 passed`
- `verify:` `pytest the three modules -m integration` -> `6 passed`
- `verify:` `pytest src/cadrumo --collect-only` -> `collection errors 9 -> 6, all six now outside entrypoints/cli/`
- `verify:` `ruff check` -> `clean`

## Notes

These three were excluded from every suite run in this campaign, and the close
review recorded the reason as "peer renames break their imports at collection".
That was true about the cause and wrong about the remedy: both breakages were
repairable inside this package, and carrying them as an exclusion rather than
fixing them meant the campaign ran with a permanently reduced denominator.

Two unrelated faults, one line each.
`test_storage_session_preconditions` imported `cadrumo.entrypoints.cli._errors`,
which a peer promoted to the public `errors.py`; the symbol it wants,
`project_cli_boundary_error`, is exported there. The other two imported
`.sessionless_root_fixtures`, but the shared fixture module is
`_sessionless_root_fixtures` -- package-internal, which is correct for a helper
shared only inside one `tests/` directory, so the import was what needed to
move, not the module.

Six collection errors remain and every one is now outside `entrypoints/cli/`:
the justificante parser pair, the sede notifications parser, the aggregation
resolver enrolment gate, and two terminal-precondition modules. They belong to
the facade-retirement campaign that blocks S07 and are not repaired here, for
the reason recorded in the third addendum -- a relocation's consumer sweep has to
land in the same commit as its move.

The campaign now carries no excluded modules of its own.
