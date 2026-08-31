---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:7f6aab9b408c9d1afd170f998b4554f47f693361310879aeb7b336f2c37fef9e'
step_id: 'S296'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
---

# Build the graded-admission schema facet over the registry snapshot, which the projection requires of every admission while every existing builder and join reads the static inspection projection instead: derive the same five reference kinds from the snapshot's own definitions, populate the legal-refs and constraint arms the static admission correctly leaves absent since the snapshot carries the definitions the inspection does not, and SHARE the edge-derivation joins with the static walk rather than writing a second copy, justifying explicitly any place the two genuinely diverge

## Scope

- `src/cadrumo/application/modelo/workspace.py schema-record builders and their S277 join helpers`
- `and focused graded-versus-static schema-facet parity and divergence tests`

## Changes

- `M` `src/cadrumo/application/modelo/workspace.py` (narrowed 4 signatures to raw tuples: `binding_schema_records`, `formula_schema_records`, `relation_schema_records`, `parameter_schema_records`; added `graded_snapshot_casilla_schema_records`, `graded_snapshot_schema_records`)
- `M` `src/cadrumo/application/modelo/tests/test_workspace.py` (updated 4 existing tests to the narrowed signatures; added the parity and divergence tests)
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace.py src/cadrumo/application/modelo/tests/test_workspace_models.py src/cadrumo/application/modelo/tests/test_workspace_manifest.py src/cadrumo/application/modelo/tests/test_workspace_producers.py -m integration -q` -> `pass` (113 passed, 1 pre-existing unrelated failure) -- run BEFORE the signature narrowing, as its own baseline
- `verify:` same suite -> `pass` (113 passed, identical count) -- run AFTER narrowing, before adding the new casilla builder, proving the narrowing is behaviour-identical for STATIC_INSPECTION
- `verify:` same suite -> `pass` (115 passed, 1 pre-existing unrelated failure) -- final, with the two new S296 tests added
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/workspace.py src/cadrumo/application/modelo/tests/test_workspace.py` -> `pass`

## Notes

Verified before building, not assumed from field names: `RegistryRevisionInspection.family_dispositions`
is copied straight from `revision.family_dispositions` at `from_revision()`
construction (`static_inspection.py:229`) -- genuinely the same mapping on
both admissions, not a same-named-different-meaning trap like the four
found earlier today.

The four shared builders (`binding_schema_records`, `formula_schema_records`,
`relation_schema_records`, `parameter_schema_records`) needed only a
signature narrowing, not new logic: `DataBindingDefinition`,
`FormulaDefinition`, `RelationDefinition` and `ParameterDefinition` are
already the identical type on `RegistryRevisionInspection` and
`RegistrySnapshot.revision`. Confirmed the four lower-level S277 edge joins
(`formula_expression_operand_references`, `formula_operand_references_for_casilla`,
`relation_source_endpoints_for_casilla`, `relation_target_endpoints_for_binding`)
were already admission-agnostic -- they take raw typed tuples, never the
inspection object -- so no changes were needed there at all.

`graded_snapshot_casilla_schema_records` is the one genuinely new function.
`ModeloWorkspaceConstraintReferenceV1` (the only type the `constraints`
field accepts) carries no constraint VALUES (sign/min/max/pattern/enum),
only a self-referential `casilla_id` marker -- so "populating the
constraints arm" means emitting that one reference when
`CasillaDefinition.constraints is not None`, empty when it declares none,
never `None` (S283's own distinction, now on the side that DOES carry the
data).

The parity test proves the shared four are byte-identical fed from a real
inspection versus a real snapshot of the SAME modelo 303 / 2026 / 1T
coordinate -- not synthetic fixtures, so it exercises the actual bundled
registry data both admissions would serve for a real filing. The divergence
test proves the same casilla's `legal_refs`/`constraints` are `None` under
static and populated under graded, on the same real casilla set.

S128 stays unchecked: this closes S296, but the full
`resolve_graded_snapshot_result` assembly wiring WORK+REGISTRY(graded)
captures, the readiness/closure ports, and all the facets together into one
validated `ModeloWorkspaceGradedSnapshotResultV1` has not been built.
