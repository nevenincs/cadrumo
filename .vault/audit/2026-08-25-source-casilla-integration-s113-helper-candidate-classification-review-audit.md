---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:a80076b4c5b9540ffe46881b0b6fd22af6de9aa00910e8ea947db85dd62f2eea'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# `source-casilla-integration` audit: `S113 helper candidate classification review`

## Scope

Independent review of `bf3128132a`, the two S112 helper call graphs, the
source-connectivity census vocabulary and governing ADR, plus the S113
research, execution record, plan, and index links.

## Findings

### temporal-selector | pass | helper enumerates authority coordinates, not source facts

`revision_selection_coordinates` takes an already loaded `ModeloRevision` and
a caller-supplied horizon, returning only law-declared filing coordinates.  Its
production callers inspect registry/construct/temporal/export coverage; none
acquires a taxpayer value, binding source, casilla target, source reference,
secure owner, provenance, replay, or export value.  The structural helper
classification is therefore correctly `not_applicable` rather than a source
candidate.

### portal-safety-factory | pass | helper creates terminal integrity refusal only

`portal_integrity_error` accepts a closed portal invariant and primitive
application-state facts, then emits a safety `PortalIntegrityError`.  All
production callers are registry metadata invariant checks.  A modelo or
revision identifier in a refusal context is not a filing fact, carrier,
resolver, destination, secure owner, lifecycle, or export route.  Its
`not_applicable` classification is correct.

### census-and-authority-boundary | pass | no promotion or new ADR is warranted

The reviewed commit has no census diff and leaves the stale helper digest
intact.  The accepted connectivity ADR already provides the closed
`not_applicable` vocabulary and refuses structural discovery as binding
authority.  Both helpers fail the ADR's source-fact and lifecycle predicate;
a new ADR would duplicate, rather than refine, that decision.  S115 remains
the designated owner of any explicit census/digest update.

### reverse-research-link | low | corrected

The S113 research linked to the plan, but the plan did not link back to this
new grounding document, leaving the feature reference gate incomplete.  The
review added the single reverse `related:` edge from the plan to the S113
research.  No plan-step wording or status changed.

## Recommendations

PASS.  Preserve both helpers as evidence-backed `not_applicable` structural
identities.  Do not add a candidate, source, binding, resolver, destination,
or digest update unless S115 independently records a governed census change.
