---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:470456227f49018885db44ad669bf6be598194cee2a59c086355c922716da76a'
step_id: 'S283'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
---

# Decide what a static-inspection casilla row of the Workspace schema record may carry, given the inspection retains casilla and legal IDENTIFIERS by design while the record requires data_type, classification, family membership, legal_refs and constraint presence: rule whether those enrich the inspection, whether the casilla row is bounded to identity alone for this admission, and in either case rule how an absent field is represented so an empty legal_refs or constraint tuple cannot silently read as none declared; amend the governing registry-api-gate decision record in the same change

## Scope

- `the amended 2026-08-24-tui-registry-api-gate-adr`
- `src/cadrumo/domain/calculations/registry/static_inspection.py`
- `src/cadrumo/application/modelo/workspace.py schema-record construction`
- `and focused casilla-row absence-versus-emptiness tests`

## Changes

- `M` `.vault/adr/2026-08-24-tui-registry-api-gate-adr.md`
- `M` `src/cadrumo/application/modelo/workspace_models.py`
- `M` `src/cadrumo/application/modelo/tests/test_workspace_models.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace_models.py -m "unit or integration" -q` -> `pass` (29 passed, 1 pre-existing unrelated failure)
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/workspace_models.py` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace.py src/cadrumo/application/modelo/tests/test_workspace_manifest.py src/cadrumo/application/modelo/tests/test_workspace_producers.py -m integration -q` -> `pass` (66 passed, no regression)

## Notes

Ruled: bound a STATIC_INSPECTION casilla row to identity alone; do not
enroll `CasillaDefinition` or its `constraints`/`legal_refs` slices onto
`RegistryRevisionInspection`. Grounded directly in the inspection's own
docstring ("the source, casilla, binding, projection, and legal
IDENTIFIERS... cannot calculate, render, or file anything" -- identifiers,
not definitions, a deliberate boundary) and in `CasillaConstraints`'s own
fields (`min_value`, `max_value`, `enum` -- declared regulatory values,
exactly the filing-adjacent content that boundary excludes). Enrolling would
have contradicted the projection's stated design rather than extended it,
unlike `review_status`/`family_dispositions`.

The harder half: `ModeloWorkspaceSchemaRecordV1.legal_refs` and
`.constraints` are now `... | None`, defaulting to `()` for every existing
graded caller. `None` = this admission's producer never carries the
underlying data for this reference kind; `()` = it does, and none is
declared. A STATIC_INSPECTION casilla row's `legal_refs`/`constraints` are
always `None`. FORMULA/BINDING/RELATION/PARAMETER rows are unaffected --
those definitions declare `legal_refs` directly, so they carry real tuples
under either admission. Proved the distinction survives construction, JSON
round-trip, and the unset default (`test_workspace_models.py`).

Explicitly left open rather than silently decided: `source_refs` has the
identical shape of problem for a casilla row (`CasillaDefinition.source_refs`
is equally absent from the inspection) but this Step did not name it, so it
stays a plain empty-tuple field. Recorded in the ADR amendment so a future
reader does not mistake the omission for a considered "no" on `source_refs`.

**Fourth field-shape incident, same pattern**: `review_status`, then
`family_dispositions`, now `legal_refs`/`constraints` are the third and
fourth instances of the shared Workspace records requiring something
`RegistryRevisionInspection` was not built to carry. The first two were
straightforward enrolments; this one required the projection to stay
identity-only AND the record's own type to grow an absence-vs-emptiness
distinction it did not have. Expect the fifth to need its own judgment about
which of these two shapes it is, rather than assuming enrolment is always
the answer.

**Third capture-race incident on an ADR file**: the staged ADR edit for this
Step landed inside a peer's `ed01a546cd` (their own S282 commit) via the
shared working tree, verified byte-identical before treating it as landed.
This is the third time a staged-but-uncommitted edit of mine has ridden into
a peer's commit today (`m303_orden_projection_compiler.py` rename,
`validate_references.py`/`verdict_cache.py` deletion, now this ADR
paragraph) -- always checked for exact-match before trusting it, never
altered.
