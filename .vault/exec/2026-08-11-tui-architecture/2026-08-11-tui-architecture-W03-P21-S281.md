---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:be65d4bba5a32df14a3fc8cdc67017b0a34cfeb4b9e5a59b105376bd7fb2f49b'
step_id: 'S281'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Correct the permitted-surface row-group category, which admits ADD_ROW, UPDATE_ROW and DELETE_ROW for every MANUAL_INPUT binding although every such binding in the registry is a statically positioned scalar copy with no row set: decide whether the repeatable-row surface is the per-modelo ModeloDetailRow union the calculate boundary already carries, retire or re-address the binding-keyed row-group entry accordingly, and amend the edit-contract decision record in the same change so no intent can address a static field under a row semantic

## Scope

- `the amended modelo-edit-contract ADR`
- `src/cadrumo/application/modelo/_edit_services.py permitted-surface projection`
- `_edit_models.py row addresses`
- `and focused row-surface admission tests`

## Changes

- `M` `.vault/adr/2026-08-24-modelo-edit-contract-adr.md`
- `M` `src/cadrumo/application/modelo/_edit_services.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_services.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_execution.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_edit_models.py src/cadrumo/application/modelo/tests/test_edit_services.py src/cadrumo/application/modelo/tests/test_revision_persistence_guarded_writes.py src/cadrumo/application/modelo/tests/test_edit_commit_point_guard.py src/cadrumo/application/modelo/tests/test_edit_execution.py src/cadrumo/application/modelo/tests/test_edit_contract.py src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py src/cadrumo/adapters/persistence/profile/tests/test_modelos_edit_receipts.py -q -n 0 -m "integration or unit"` -> `pass` (53 passed)
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/_edit_services.py src/cadrumo/application/modelo/tests/test_edit_services.py src/cadrumo/application/modelo/tests/test_edit_execution.py src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/_edit_services.py src/cadrumo/application/modelo/tests/test_edit_services.py src/cadrumo/application/modelo/tests/test_edit_execution.py src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py` -> `pass`

## Notes

Decision: `_writable_row_group_entries` now returns no entries, unconditionally,
for every current registry revision, since no registry `manual_input` binding
matches a genuine row-set shape (every one is a static scalar
`aggregation = {op = "copy"}`, none carries a row index). `_validate_row_intent`
therefore refuses every row intent as `DISALLOWED_INTENT` -- a correct,
evidence-grounded refusal, not a dormant placeholder.

`_edit_models.py` is untouched, deviating from the Step's own named scope:
the row-intent/address model vocabulary (`ModeloEditRowIntentKind`,
`ModeloEditRowAddressV1`, `ModeloEditWritableRowGroupSurfaceEntryV1`) is
retained rather than deleted or re-addressed, because the `BindingId` +
row-index shape is not inherently wrong -- only unpopulated by current
registry data -- and stays correct if a genuine binding-keyed row set is ever
added. Re-addressing it to `ModeloDetailRow`'s keying was considered and
rejected for this Step: `ModeloDetailRow` rows are keyed by per-modelo
business fields, not `BindingId` + row index, so this would be a new surface
entry kind, not a re-keying of the existing one, and building it now would
require inventing a per-modelo detail-row eligibility authority the registry
does not yet expose (today it is implicit in CLI `--row` subcommand routing).
The ADR amendment records this as deferred future work rather than deciding
it ahead of that authority existing, to avoid repeating this Step's own
root-cause pattern (modelling ahead of registry data).

`_MANUAL_INPUT_SOURCE` module constant in `_edit_services.py` was removed as
dead code once `_writable_row_group_entries` stopped referencing it.
