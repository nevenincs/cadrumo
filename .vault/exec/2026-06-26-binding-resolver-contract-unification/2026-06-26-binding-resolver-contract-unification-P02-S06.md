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

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-resolver-contract-unification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-06-26-binding-resolver-contract-unification-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Promote the borrador mesh resolver result onto CalculationSourceResolution and drop the Modelo100BorradorBindingResult wrap, preserving the borrador_snapshot_id and bindings_sourced_from_borrador provenance trace the downstream observation builder consumes and ## Scope

- `src/aeat/application/modelo/_borrador_binding.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
