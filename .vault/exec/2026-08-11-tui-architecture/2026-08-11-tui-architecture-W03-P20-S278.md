---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:c26aea8f23fad8ef5825b2c1a5428d141c864502c8bbf5b24b9593c01866153b'
step_id: 'S278'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
---

# Decide and record what the field manifest means for the static-inspection admission, which the governing decision record lists as capturing field_manifest while the only generator walks the snapshot-rooted type universe a static inspection never loads: either root a second generator at the inspection's own type universe, or define the snapshot-rooted manifest as the single universe with per-admission availability, and rule out the third reading of a degraded result presented as a complete one; amend the governing registry-api-gate decision record in the same change and prove the chosen manifest digest is stable and admission-honest

## Scope

- `the amended 2026-08-24-tui-registry-api-gate-adr`
- `src/cadrumo/application/modelo/workspace_manifest.py`
- `and focused static-admission manifest tests`

## Changes

- `M` `.vault/adr/2026-08-24-tui-registry-api-gate-adr.md`
- `M` `src/cadrumo/application/modelo/workspace_manifest.py`
- `M` `src/cadrumo/application/modelo/workspace_producers.py`
- `M` `src/cadrumo/application/modelo/workspace.py`
- `M` `src/cadrumo/application/modelo/tests/test_workspace_manifest.py`
- `M` `src/cadrumo/application/modelo/tests/test_workspace.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace_manifest.py src/cadrumo/application/modelo/tests/test_workspace.py src/cadrumo/application/modelo/tests/test_workspace_producers.py -m integration -q` -> `pass` (58 passed: 22 + 13 + 23)
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/workspace.py src/cadrumo/application/modelo/workspace_manifest.py src/cadrumo/application/modelo/workspace_producers.py` -> `pass`

## Notes

Decision: root a SECOND generator (`generate_modelo_workspace_field_manifest_for_inspection`)
at `RegistryRevisionInspection`'s own type universe. Rejected the "single
snapshot-rooted universe with per-admission availability" reading on the
governing ADR's own precedent: it already refuses to represent the REGISTRY
projection itself as "one degraded result" across the two admission grades
("Static revision inspection and a grade-admitted snapshot make different
authority claims and cannot be represented as one degraded result"), and the
identical reasoning holds for the manifest with no less force -- a
snapshot-rooted manifest with most rows marked unavailable for static
inspection is exactly the "degraded result presented as complete" shape the
Step required ruling out.

The second generator is not a second hand-authored copy of the classification
rules: it reuses `_classify_node`/`_projected_destination` verbatim over a
new root, since the underlying registry-compiler types
(`FormulaDefinition`, `DataBindingDefinition`, `RelationDefinition`,
`ProjectionEndpointDeclaration`, and the identity kinds they carry) are the
exact same types `RegistrySnapshot.revision.*` already walks -- only the
container shape differs (`RegistryRevisionInspection` strips CasillaDefinition
bodies down to bare `frozenset[CasillaId]`, for instance). Two small additions
were needed: `_INSPECTION_ROOT_FIELDS` (the inspection's own top-level field
denominator, structurally distinct from `_REGISTRY_ROOT_FIELDS` since the
inspection deliberately excludes filing-grade content) and extending the
existing `review_status` DERIVED rule to cover both roots' paths. No
`derived.export_layout.*` root exists for the inspection root, since
`RegistryRevisionInspection` carries no full `ModeloRevision` to derive
layouts from; the `selector.*` roots are shared unchanged (pure function of
`BindingSourceKind`, independent of admission).

Verified against the real bundled registry (modelo 130, 2026, 1T and modelo
303, 2025, 4T): the generated manifest is a stable fixed point (identical on
regeneration, same digest), carries a distinct digest and distinct traversal
roots from the snapshot-rooted manifest at the identical coordinate, and
never reaches a materialization/verification/`filed_at` path -- proven as a
structural property of the walked type, not a filter, since
`RegistryRevisionInspection` has no such fields to reach in the first place.

`ModeloWorkspaceFieldManifestPortV1` now takes `authority:
RegistrySnapshot | RegistryRevisionInspection` and dispatches to the matching
generator/comparison-domain function; had no existing constructors anywhere
in the tree, so the signature change broke no caller.

Flipped `SCHEMA_INSPECTION`'s S279 capability disposition from provisional to
`AVAILABLE` for STATIC_INSPECTION in the same commit, since `field_manifest`
is now a real contributor for that admission; the other four capabilities are
unchanged (`UNMEASURED`, per S279).
