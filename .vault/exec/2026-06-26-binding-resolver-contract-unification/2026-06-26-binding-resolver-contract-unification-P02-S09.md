---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S09'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---




# Update the calculate orchestration call site to consume the mesh-merged resolution directly instead of CalculationBindingResolution, sourcing borrador provenance from the borrador resolution, applying the apply-cached-on-collision drive against the live peer WIP

## Scope

- `src/aeat/application/modelo/_calculation_actions.py`

## Description

- Rewrite the calculate orchestration call site (`calculate_modelo_revision`) to consume the precedence-merged source resolution directly instead of the deleted wrap function.
- Delete `resolve_calculation_binding_inputs` and `CalculationBindingResolution` per no-legacy; re-home the post-merge helpers (engine-channel-mismatch refusal, previous-filing casilla-override lift, declaration-period informational inputs) as PUBLIC functions in `_binding_resolution`, and expose the profile / borrador tier builders as `resolve_profile_source_tier` / `resolve_borrador_source_tier`.
- Source borrador provenance from the merged resolution's typed `BorradorSourceProvenance` (snapshot id + sourced-binding trace) handed to `persist_calculation_revision`.

Modified files: `src/aeat/application/modelo/_calculation_actions.py`, `src/aeat/application/modelo/_binding_resolution.py`.

## Outcome

Landed in the S07+S09 commit `5620ed7f5`. The binding-resolution wrap is gone; the single envelope flows from the resolvers through the precedence merge to the engine. Behaviour-preserving: the resolved bindings / enum / date channels and the resolved-inputs assembly are identical to the prior path. No casilla shift - the M130->M100, M303->M390, recargo, and pull-vs-calculate parity E2E green; the 73 binding tests green; collect-only clean; ruff clean.

## Notes

The only consumer of the deleted symbols was the rewritten call site itself. The `_calculation_actions.py` hunks were landed through the apply-cached own-only drive (the file carries the `_pre_mesh_handled` peer WIP); the staged index was verified to carry zero foreign markers before commit. A peer had separately staged three unrelated files into the shared index (an M100 settlement-completeness test plus two verification-predicate TOMLs); those were reverse-applied out of the index (working tree untouched) so the commit carried only the four authored files.
