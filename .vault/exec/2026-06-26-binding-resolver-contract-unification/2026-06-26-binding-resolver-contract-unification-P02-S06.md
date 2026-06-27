---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S06'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---




# Promote the borrador mesh resolver result onto CalculationSourceResolution and drop the Modelo100BorradorBindingResult wrap, preserving the borrador_snapshot_id and bindings_sourced_from_borrador provenance trace the downstream observation builder consumes

## Scope

- `src/aeat/application/modelo/_borrador_binding.py`

## Description

- Add a typed `BorradorSourceProvenance` sub-model (snapshot id + sourced-binding tuple) to the source-mesh module and carry it as an optional `borrador_provenance` field on `CalculationSourceResolution`, preserving the borrador snapshot trace the persistence boundary consumes without accreting per-source named fields on the generic envelope (coordinator decision option a, lead-refined to one typed sub-model).
- Change `resolve_modelo_100_borrador_bindings` to return `CalculationSourceResolution` directly, stamping `borrador_provenance` from the loaded snapshot id and the sorted sourced-binding set plus the per-binding `CalculationSourceProvenance` rows.
- Delete the `Modelo100BorradorBindingResult` wrap class and drop it from the module and package `__all__`; keep the `Modelo100BorradorBindingCommand` input contract unchanged.
- Simplify `Modelo100BorradorSourceResolver.resolve` to delegate straight to `resolve_modelo_100_borrador_bindings`.
- Preserve the trace through `merge_source_resolutions`: the borrador resolution is the sole contributor of a non-None `borrador_provenance`, carried last-writer-wins onto the merged result.

Modified files: `src/aeat/application/aggregation/_source_mesh.py`, `src/aeat/application/aggregation/__init__.py`, `src/aeat/application/modelo/_borrador_binding.py`, `src/aeat/application/modelo/__init__.py`.

## Outcome

Landed in the atomic S05+S06+S08 commit `0d825d774`. The borrador snapshot id and sourced-binding trace now ride a typed channel read directly at the calculate call site (never parsed from provenance source_refs), so `persist_calculation_revision` receives the identical `borrador_snapshot_id` + `bindings_sourced_from_borrador` it did before. The end-to-end borrador calculate test and the resolver-parity test stayed green; no casilla value shift.

## Notes

The resolver path now stamps the snapshot id from the loaded `snapshot.snapshot_id` rather than re-stamping the caller's input arg, which is the more correct provenance source and matches the existing test expectations. `test_borrador_binding` carried concurrent peer WIP (a casilla-id-validation sweep); my result-shape migrations were landed through the apply-cached own-only drive, leaving that peer WIP intact in the working tree.
