---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:ca8403ad5f39780682d29925828794e7c9ae5c82acfb2143010d0324541e228d'
step_id: 'S280'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Scope the operator binding-override edit surface that REMOVE_OVERRIDE was modelled for: decide whether an override of a binding-computed casilla is addressed by casilla or by binding, admit it as its own permitted-surface entry kind rather than a manual scalar, and either re-address the intent to the store it targets or record that the scalar-addressed spelling is retired; amend the edit-contract decision record in the same change

## Scope

- `the amended modelo-edit-contract ADR`
- `src/cadrumo/application/modelo/_edit_models.py`
- `_edit_services.py permitted-surface projection`
- `and focused binding-override admission tests`

## Changes

- `M` `.vault/adr/2026-08-24-modelo-edit-contract-adr.md`
- `M` `src/cadrumo/application/modelo/_edit_models.py`
- `M` `src/cadrumo/application/modelo/_edit_services.py`
- `M` `src/cadrumo/application/modelo/_edit_execution.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_models.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_services.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_execution.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_edit_models.py src/cadrumo/application/modelo/tests/test_edit_services.py src/cadrumo/application/modelo/tests/test_revision_persistence_guarded_writes.py src/cadrumo/application/modelo/tests/test_edit_commit_point_guard.py src/cadrumo/application/modelo/tests/test_edit_execution.py src/cadrumo/application/modelo/tests/test_edit_contract.py src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py src/cadrumo/adapters/persistence/profile/tests/test_modelos_edit_receipts.py -q -n 0 -m "integration or unit"` -> `pass` (58 passed)
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/_edit_models.py src/cadrumo/application/modelo/_edit_services.py src/cadrumo/application/modelo/_edit_execution.py src/cadrumo/application/modelo/tests/test_edit_models.py src/cadrumo/application/modelo/tests/test_edit_services.py src/cadrumo/application/modelo/tests/test_edit_execution.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/_edit_models.py src/cadrumo/application/modelo/_edit_services.py src/cadrumo/application/modelo/_edit_execution.py src/cadrumo/application/modelo/tests/test_edit_models.py src/cadrumo/application/modelo/tests/test_edit_services.py src/cadrumo/application/modelo/tests/test_edit_execution.py` -> `pass`

## Notes

Decision: address by BINDING, not casilla. `REMOVE_OVERRIDE` is retired from
`ModeloEditScalarIntentKind`; a new `ModeloEditBindingAddressV1`
(`binding_id`-keyed), `ModeloEditBindingIntentKind`
(`SET_OVERRIDE_VALUE`/`REMOVE_OVERRIDE`), `ModeloBindingEditIntentV1`, and a
new writable/non-writable binding-override permitted-surface entry pair
address `CalculationRevision.binding_overrides` directly.

Unlike the row-group correction, a real, already-tested eligibility
authority existed to ground this surface: `_writable_binding_override_entries`
reuses the exact gate the CLI's `--binding KEY=VALUE` override already runs
(`_reject_caller_overrides_of_source_bindings`'s `BUCKET_AGGREGATION_LOCK_SOURCES`
exclusion in `_calculation_actions.py`), plus a date-channel exclusion
mirroring the real CLI's own `--binding` refusal for date-consumed bindings.
Modelo 131's ninety-seven `manual_input` bindings -- wrongly surfaced as row
groups before the row-category correction -- now correctly surface here
instead, proven by a real test against the bundled registry.

Guarded execution/persistence for a binding-override intent (a
`cleared_casilla_ids`-equivalent axis threaded through the calculate
boundary) is deferred: every binding intent refuses today with a typed
`ModeloEditUnsupportedIntentReason`, matching the row-intent precedent. This
Step's scope covers the decision, the address/intent/surface models, and
admission; execution wiring is future work.
