---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:2e0c3cfbca98c47af3d547e0cd52ea242bc5452d39bc8f99c9deb9b919b203f9'
step_id: 'S115'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Widen the folder-import fold so a directory import reports every file's validation and verification report, not only the first

## Scope

- `src/cadrumo/application/ledger/models.py`

## Changes

- `M` `src/cadrumo/application/ledger/models.py`
- `M` `src/cadrumo/application/ledger/actions_import.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_import_cli.py`
- `M` `src/cadrumo/application/ledger/tests/test_actions_import_export.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_ledger_import_ux.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_workflow_surface.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_ledger_status_import_payload_contract.py`
- `verify:` folded three results -> 3 validations and 3 sources kept, in file order
- `verify:` `pytest application/ledger + the two CLI import suites -k import -n 0 -m ""` -> pass (71)

## Notes

The fold carried its own narrowing note: "validation and source are per-FILE
reports and only the first survives... widening those fields to tuples is a
shape change this fold cannot make on its own." So a directory import reported
ONE file's validation as though it spoke for the import, and the other files'
findings were unreachable.

Widened end to end: the record holds tuples, both producers wrap their single
report in a one-tuple, the fold concatenates them with the reference tuples it
already concatenated, and the renderer prints each file's block instead of one.

A single-file import carries a one-tuple rather than keeping a scalar beside the
tuple. That matters more than it reads: the single and the many are now the same
type, so no caller has to tell them apart, and the fold has nothing to special-
case. It is also why four test files changed -- the wire key went from
`validation` to `validations`, and this project carries no released data, so the
rename is the whole migration.

Probed the actual defect rather than only the tests: three results folded keep
three validations and three sources, in file order.

### One failure in this area is NOT this

`test_one_poisoned_file_does_not_discard_the_rest_of_the_folder` fails, and it
is worth naming because it sits in the same feature and sounds like this step.
It is not. The folder LOOP re-raises on the first `TransactionValidationError`
and aborts the run, which is the behaviour that test was written to forbid --
its own comment says "under the old comprehension it aborted the run before
either good file was reached". The loop is untouched by this change; the diff
here is the renderer and the shapes. A partial-success folder import is a
different fix from a fold that keeps every report.
