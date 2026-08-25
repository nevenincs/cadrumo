# Registry facade family census — working S175 audit

## Scope and chronology

`c94133f29516b12e3529f3d154c31592562f6198` is the already-delivered mechanical
private-to-public registry relocation. It renamed exactly 78 modules under
`src/cadrumo/domain/calculations/registry`, changed consumers to direct module
imports, and left `registry/__init__.py` inert. This audit does not replay that
move, restore a private module, or introduce a compatibility surface.

S173 work had begun against the recovered authority mapping before the plan was
corrected to make S175 its predecessor. The shared-tree work therefore only
repairs direct defining-owner routes and authority semantics; it does not claim
an S175 disposition. In particular, post-c941 owner discoveries are recorded
separately from this fixed historical family and are not smuggled into its 78
rows.

## Discovery and exact census

Semantic discovery used the canonical Vaultspec-RAG search for registry facade
relocation and authority ownership, followed by the exact historic command:

```powershell
git diff-tree -r -M --name-status --format= c94133f295^ c94133f295 -- src/cadrumo/domain/calculations/registry
```

Its rename-filtered result is exactly 78 one-to-one rows. The scoped generator
`dev/quality/registry_facade_family_census.py` derives only this set, historic
facade exports from the parent `__init__.py`, and current AST/text consumers
under `src/`, `dev/`, and `docs/`. It is intentionally family-specific rather
than a new generic scanner.

## Current adjudication state

`registry_facade_family_census.v1.json` is a deterministic template, not an
approval record. It has all 78 historic identities, export lists, and consumer
categories, but deliberately carries no semantic-owner, evidence, disposition,
or follow-on Step values yet. `--check` therefore fails closed until an
independent architecture review records a human semantic adjudication for every
row and the canonical plan CLI has minted a unique bounded Step for each one.

This is intentional: inferring `keep_public` from a filename or a mechanical
rename would violate S175. No completion claim is made for S175 or S173 by this
audit.

## Required review handoff

The reviewer must populate exactly one of `keep_public`, `hard_move_complete`,
`privatize_external_elimination`, or `delete` for each row, explain the semantic
owner from code/architecture evidence, assign a unique canonical follow-on Step,
run `python dev/quality/registry_facade_family_census.py --check`, then amend
the plan through its CLI. The final package gate remains separate: zero project
package binding, zero re-export, and zero unresolved family rows.
