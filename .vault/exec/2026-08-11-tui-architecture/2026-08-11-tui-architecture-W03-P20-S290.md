---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:2b5e385dcc915817b25a7fcfcc3e629aa03561e33e3052a231e17632be00ef7c'
step_id: 'S290'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
---

# Decide how a graded-snapshot provenance record names its subject, since the workspace provenance record requires the casilla or binding identity a trace explains while the persisted calculation source ref carries only resolver identity, resolved binding source, source-object reference and fingerprint, with no field naming the subject and no shared key to join on: rule whether the persisted trace gains a subject identity, whether the provenance facet is keyed by resolved binding source instead, or whether a per-subject provenance record cannot be produced from what is persisted; amend the governing registry-api-gate decision record in the same change

## Scope

- `the amended 2026-08-24-tui-registry-api-gate-adr`
- `src/cadrumo/domain/modelos/_calculation_revision.py CalculationSourceRef`
- `src/cadrumo/application/modelo/workspace_models.py provenance record`
- `and focused provenance-subject tests`

## Changes

- `M` `src/cadrumo/domain/modelos/_calculation_revision.py` (`CalculationSourceRef.source_casilla_ids`, id-derivation payload updated)
- `M` `src/cadrumo/application/modelo/_calculation_actions.py` (`_source_provenance_refs` passes `source_casilla_ids` through)
- `M` `src/cadrumo/adapters/persistence/profile/tests/test_source_mesh_revision_roundtrip.py` (populated the new field non-default, per the roundtrip fixture's own stated contract)
- `M` `src/cadrumo/application/modelo/workspace.py` (`graded_snapshot_provenance_facet`)
- `M` `src/cadrumo/application/modelo/tests/test_workspace.py` (`test_graded_snapshot_provenance_facet_fans_out_by_linked_casilla_and_drops_unlinked_refs`)
- `M` `.vault/adr/2026-08-24-tui-registry-api-gate-adr.md` (S290 amendment)
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/workspace.py src/cadrumo/domain/modelos/_calculation_revision.py src/cadrumo/application/modelo/_calculation_actions.py src/cadrumo/application/modelo/tests/test_workspace.py src/cadrumo/adapters/persistence/profile/tests/test_source_mesh_revision_roundtrip.py` -> `pass` (only pre-existing unrelated diagnostics, reconfirmed against HEAD content)
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace.py src/cadrumo/application/modelo/tests/test_workspace_models.py src/cadrumo/application/modelo/tests/test_workspace_manifest.py src/cadrumo/application/modelo/tests/test_workspace_producers.py src/cadrumo/domain/modelos/tests/test_calculation_revision.py src/cadrumo/adapters/persistence/profile/tests/test_source_mesh_revision_roundtrip.py -m "unit or integration" -q` -> `pass` (177 passed, 1 pre-existing unrelated failure)

## Notes

Verified, before ruling, that no other persisted structure already recovers
the casilla-to-source link: `CasillaObservation.source_refs` is a different
namespace (legal-catalogue `SourceRefId`s, not resolver-mesh source refs);
`operand_refs`/`operand_casilla_refs` are formula-tree lineage, not
resolver-mesh source lineage; `row_casilla_provenance` covers only
row-materialized casillas. No recoverable join exists, which forces option
(a) per the plan Step's own framing.

Team lead's correction changed the shape of the finding: the earlier report
described option (a) as reversing a documented design choice. It is not.
`CalculationSourceRef`'s docstring states its `legal_refs`/`source_refs`
omission and gives an anti-duplication reason scoped to per-casilla
regulatory grounding; it says nothing about `source_casilla_ids`, and that
rationale does not extend to a subject identity. The application-side
`CalculationSourceProvenance` already carried `source_casilla_ids`
end-to-end -- the domain projection simply never carried it across the
application-to-domain boundary. Fixed at that exact boundary
(`_source_provenance_refs`), in the same commit as the id-derivation payload
update (so a save-drops-field regression on the new field is not invisible)
and the roundtrip fixture update (the fixture's own docstring claims every
field is populated non-default; left unpopulated it would have made this
exact regression class invisible on the one boundary designed to catch it).

Scoped deliberately narrow, matching the plan Step's own file list: this
lands the domain field, the boundary pass-through, and the Workspace facet.
It does NOT backfill `source_casilla_ids` at the 16 `CalculationSourceProvenance`
construction sites across 7 application-layer files that do not yet populate
it (spot-checked one, `_modelo_bindings.py`'s ledger IVA aggregation
provenance, and confirmed it leaves the field at its `()` default). Those
resolvers producing zero provenance records today is the honest, non-fabricated
consequence of that gap, not a defect in this change -- populating each
resolver is a separate undertaking, several of which would need the
registry's own binding-to-casilla wiring (the same kind of join S277 already
built for schema_facet) rather than a trivial field copy.
