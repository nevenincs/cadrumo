---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S08'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---




# Remove the BindingSourceResolution Protocol and the resolve_calculation_binding_inputs B-to-A-to-B wrap, re-homing the channel-mismatch and previous-filing-override helpers onto the mesh-merged resolution, applying the apply-cached-on-collision drive against the live peer WIP

## Scope

- `src/aeat/application/modelo/_binding_resolution.py`

## Description

- Remove the `BindingSourceResolution` Protocol; the two former members (`ProfileSourcedBindingResult` / `Modelo100BorradorBindingResult`) are gone, so the structural role is no longer needed.
- Rewrite `resolve_calculation_binding_inputs` to consume the profile and borrador resolvers' `CalculationSourceResolution` directly, ending the B-to-A-to-B round-trip (resolver -> wrap result -> re-merge). The two `_resolve_*_for_calculation` helpers now return `CalculationSourceResolution`.
- Re-home the channel-mismatch rejection and the previous-filing casilla-override lift unchanged onto the resolution-driven merge; the precedence dict-merge (profile lowest, mesh backend, borrador, caller highest) is byte-identical.
- Change `CalculationBindingResolution` to carry the typed `borrador_provenance` instead of the two retired result wraps; the calculate call site reads `borrador_provenance.snapshot_id` / `.bindings_sourced` typed and hands them to `persist_calculation_revision`.
- Delete the obsolete role test and the wrap-validator tests; migrate `test_profile_binding` and `test_borrador_binding` to the typed shape.

Modified files: `src/aeat/application/modelo/_binding_resolution.py`, `src/aeat/application/modelo/_calculation_actions.py` (call-site borrador read), `src/aeat/application/modelo/tests/test_profile_binding.py`, `src/aeat/application/modelo/tests/test_borrador_binding.py`, and the deleted `test_binding_source_resolution_role.py`.

## Outcome

Landed in the atomic S05+S06+S08 commit `0d825d774`. The B-to-A-to-B wrap is gone; profile and borrador resolve on one envelope. `resolve_calculation_binding_inputs` keeps its signature and `CalculationBindingResolution` return so the call site stays green at this commit; the full deletion of `resolve_calculation_binding_inputs` and the mesh enrollment of profile + borrador are S07+S09 (the next commit, gated on lead review of the P02 diff).

## Notes

Sequencing note for the coordinator: the brief's logical step order (S05, S06, S08, then S07, S09) plus the approved atomic grouping (S05+S06+S08 in one commit, S07+S09 in the next) means `resolve_calculation_binding_inputs` and `CalculationBindingResolution` cannot be fully deleted in this commit without breaking the call site before S09 rewrites it. They are therefore retained, wrap-free, in this commit and removed in the S07+S09 commit, keeping every commit green and behaviour-identical. `_calculation_actions.py` carries the live `_pre_mesh_handled` peer WIP; my one-line call-site borrador read was staged through the apply-cached own-only drive (verified zero foreign markers in the index) leaving that WIP intact for S07.
