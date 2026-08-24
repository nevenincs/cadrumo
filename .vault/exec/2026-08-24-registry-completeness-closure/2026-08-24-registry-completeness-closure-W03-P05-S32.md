---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:2876e7bea1f4667d356b1fc3f8988f70ea803e30dbf36edffede6143db9c9ab8'
step_id: 'S32'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# Verify binding selectors, resolver enrollment, calculation paths, and provenance for every filing-grade revision

## Scope

- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Use Vaultspec-RAG semantic discovery, then inspect the binding selector and
  validator registries, production calculation-route ownership, source-mesh
  policy, filing-value provenance builder, and source-connectivity census.
- Derive the filing-grade corpus from `bundled_authority()` and select every
  member through the FILING-grade snapshot boundary; do not maintain a
  hand-authored modelo/revision list.
- Add the missing exact `193/2024/0A/gasto193_contributor` census destination
  beside the existing 2025-and-later destination.
- Add a derived test gate for selector validation, calculation-route
  disposition, deferred-source census ownership, and verbatim binding-value
  provenance, with wrong-selector, removed-census-owner, and removed-legal-ref
  mutation bites.
- Audit authority surfaces for redeclaration: the gate reads the existing
  selector accessor, route disposition map, and census rather than copying any
  source taxonomy, resolver enrollment table, or plan-owner mapping.

## Outcome

The live authority derives 66 FILING-grade revisions, 61 of which expose
bindings, with 9,150 binding declarations. The gate covers this generated
corpus and makes a deferred source visible only when its exact revision
coordinate has one bounded census owner.

This is verified/owned, not fully enrolled. The filing-grade deferred families
remain intentionally unresolved: Modelo 232's related-party source remains in
the accepted S92-S95 route, Modelo 360's refund source remains in S96-S99, and
Modelo 193's contributor source remains in S104-S107. Their authoritative
source-connectivity dispositions and bounded actions remain the source of
truth; this step does not promote any of them to an enrolled resolver.

The new gate passed `ruff check`. Re-running its production import path and
the focused census suite is currently blocked by concurrent worktree state:
`cadrumo.application.auth._operation_definitions` imports
`OperationExecutorContext` from `cadrumo.application.operations`, but that
name is not presently exported. The failure occurs during test collection on
the production `application.registry` -> `application.modelo` import chain.
S32 deliberately remains open until the peer import surface is restored and
the focused tests can be rerun.

## Notes

- No peer worktree files were modified and no production import boundary was
  bypassed. No data was removed.
- Exact code searches confirmed one `DataBindingDefinition` authority, one
  `ModeloBindingValue` schema, one binding selector/validator dispatch, and
  one calculation-route ownership declaration. The new gate adds no duplicate
  authority declaration.
