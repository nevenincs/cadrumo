---
tags:
  - '#exec'
  - '#retenciones-perceptor-count'
date: '2026-06-25'
modified: '2026-06-25'
step_id: 'S06'
related:
  - "[[2026-06-24-retenciones-perceptor-count-plan]]"
---

# Enroll the resolver in merge_source_resolutions and add the source kind to _BUCKET_AGGREGATION_OWNED_SOURCES so no source is dormant

## Scope

- `src/aeat/application/modelo/_calculation_actions.py`

## Description

- Phase P02 (S04 source-kind enum + parity gate, S05 resolver + materialisation, S06 mesh enrollment) landed atomically by teammate r2-autonomo-130-eoy as commit `699b73dfe` (10 files, 518 green, pushed no-force).
- S04: added `BindingSourceKind.RETENCIONES_AGGREGATION` (reads the dedicated P01 store, not the ledger) plus the registry-vs-enum parity gate entry in `src/aeat/core`.
- S05: added `RetencionesAggregationSourceResolver` (in `_modelo_bindings.py`) reading the P01 per-perceptor store for the modelo annual window, calling the validated `aggregate_retenciones_180` distinct-NIF primitive, materialising the perceptor-count binding via `total_perceptors`; per-family `_retenciones_bindings.py` carries the validator + materialisation; empty-store no-silent advisory carried from the ADR.
- S06: enrolled the resolver in `merge_source_resolutions` and added the source kind to `_BUCKET_AGGREGATION_OWNED_SOURCES` in `_calculation_actions.py` so no source is dormant; reserved-undeclared until P03 re-stamps the M180/190/193 bindings.

## Outcome

The retenciones distinct-perceptor source is enrolled in the live calc mesh, reading the one P01 store both surfaces share. Landed WITHOUT disturbing the live casilla-id sweep co-resident in `_calculation_actions.py` + `_bindings.py` + registry `__init__.py`: the 7 casilla-id-clean files were staged directly; the 3 entangled files were staged via `git apply --cached` of a HEAD-anchored own-edits-only patch (the interleaved registry `__init__.py` `__all__` hunk reconstructed via `git show HEAD:` + insert-after-anchor), so only the enrollment lines entered the index. Coordinator verification on origin: the committed `_calculation_actions.py` carries the enrollment (3x `RetencionesAggregationSourceResolver`) and zero `validate_casilla_input_ids`; the casilla-id WIP remains intact in the working tree (4x markers) for its owner to commit cleanly on top. 518 working-tree tests green (`test_source_resolver_enrollment` now pins 12 resolvers; resolver + parity + build-validation + full aggregation suite); py_compile clean on all changed files. P02.S04/S05/S06 closed.

## Notes

- The atomic commit was achieved across a live shared working tree via the `git apply --cached` index-only drive (no `git add -p`, no discard, no reconstruct of peer work); the staged set was verified to carry 0 casilla-id sweep markers before a no-pathspec commit. An earlier coordinator retraction of this drive (after a peer hit a shared-index foreign-staged-work gate + a genuinely interleaved hunk) was premature; r2's temp-reconstruct for the interleaved hunk + pre-commit staged-set verification proved it safe.
- P03 (M180/190/193 cutover + pull==calculate parity) is intentionally deferred: it re-points bindings on the registry surface the casilla-id sweep + the M303 #2 work are actively churning. The `_RESERVED_UNDECLARED` entry self-removes when the binding re-stamps (spuriously_reserved gate).
