---
tags:
  - '#adr'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:2dd53ee97d5604839990c2f1095a704f801e1f16f891ad0d78ff28f222f41620'
related:
  - "[[2026-08-22-source-casilla-integration-research]]"
  - "[[2026-08-22-modelo-work-binding-architecture-reference]]"
  - "[[2026-08-22-modelo-work-binding-architecture-inventory-gap-verification-reference]]"
  - "[[2026-06-10-calculation-aggregation-taxonomy-adr]]"
  - '[[2026-08-22-source-casilla-integration-composite-provenance-research]]'
---
# `source-casilla-integration` adr: `ratcheted source-domain-to-casilla connectivity` | (**status:** `accepted`)

## Problem Statement

The calculation architecture guarantees that every registry-declared binding source is enrolled, explicitly deferred, or reserved, but it does not guarantee that every existing typed source domain which should feed a filing has been declared and connected. `2026-08-22-source-casilla-integration-research` establishes this upstream blind spot and the need for a durable responsibility that remains measurable as the application grows.

The decision must define how candidates enter that responsibility, how legal identity is adjudicated, what constitutes a complete connection, and how continuing discovery is represented without an implementation plan that can never honestly complete.

## Considerations

- Existing downstream source enrollment and no-silent-blank behavior remain authoritative and must not be duplicated or weakened; `2026-08-22-source-casilla-integration-research`.
- Source and casilla terminology does not establish substitutability; target revision, legal meaning, constraint shape, grain, sign, units, and override policy must agree; `2026-08-22-modelo-work-binding-architecture-inventory-gap-verification-reference`.
- Manual input, formal deferral, not-applicable classification, and deletion are legitimate dispositions; automation is not presumptively correct; `2026-08-22-source-casilla-integration-research`.
- Continuing responsibility needs monotonic state and recurring audit, while every implementation slice needs finite authorization and completion criteria.
- The established resolver, provenance, secure-storage, and registry-binding contracts are extension points, not targets for a parallel integration architecture; `2026-06-10-calculation-aggregation-taxonomy-adr` and `2026-08-22-modelo-work-binding-architecture-reference`.

## Considered options

### Permanently open roll-up plan

Keep one L3 plan open indefinitely and append every discovered connection. This centralizes visibility but has no stable completion condition, conflates discovery with authorization, accumulates stale rows, and lets a campaign narrow its own standing goal.

### Pre-enumerated source mega-plan

Census the current tree once and plan every candidate together. This provides an apparent endpoint but falsely assumes the initial census and legal mappings are complete, and couples unrelated evidence dependencies into one execution stream.

### Inventory-only feature

Connect the known inventory domain and close. This yields immediate value but leaves the upstream discovery blind spot intact and repeats the same failure for fincas, deferred row sources, and future domains.

### Ratcheted census plus finite vertical slices

Establish one canonical connectivity census and recurring audit, bootstrap the mechanism through a finite plan, and authorize each accepted source-to-casilla connection as a bounded vertical slice with its own grounding and lifecycle. This retains continuous responsibility without an immortal implementation plan.

## Constraints

- A candidate cannot become implementation-ready until official evidence settles modelo, revision window, target semantic role, source fact, aggregation, sign, units, rounding, temporal window, entity/activity grain, absence semantics, and override policy.
- Candidate discovery from names or numeric casilla identifiers is advisory only and cannot author a binding.
- The census uses a closed disposition set: `connected`, `connect_candidate`, `grounding_blocked`, `ingress_blocked`, `registry_blocked`, `manual_by_design`, `duplicate_or_stale`, and `not_applicable`.
- Every census row carries re-fetchable grounding, an owner, and a linked bounded follow-up or explicit review condition where unresolved.
- Existing `BindingSourceKind`, source-disposition parity, `ModeloSourceResolver`, `CalculationSourceResolution`, registry validation, and encrypted `CalculationRevision` remain the only production integration path.
- Inventory is the first known candidate, not a pre-decided mapping. Its current signed helper and current M100 inventory boxes require tax adjudication before implementation.
- Documentation approval and implementation-plan approval remain independent user gates.

## Implementation

Create a finite bootstrap feature that derives the registry-side inventory of manual casillas, declared bindings, relations, formulas, and source dispositions from validated snapshots; enumerates typed source domains, secure repositories, supported ingress, row assemblers, readiness declarations, and exported calculation helpers; and joins them only through evidence-backed candidate records.

Persist the resulting census in one canonical machine-checkable form with the closed dispositions above. Add a monotonic gate that refuses unclassified new capability, unexplained disappearance or regression of accepted candidates, expired deferrals without linked action, and a `connected` claim lacking resolver ownership plus encrypted calculation-revision proof. Semantic-name matches remain report-only.

For every `connect_candidate`, require an official-source adjudication followed by one vertical slice through the existing architecture: canonical source taxonomy, typed selector validation, registry binding and casilla linkage, enrolled resolver, precedence and collision policy, diagnostics, source identity and fingerprint provenance, secure revision round trip, operator-path anti-dormancy proof, conflict proof, and replay/review/export proof where supported.

The bootstrap plan establishes the census and ratchet and adjudicates inventory as its first known candidate. It may implement inventory only if that adjudication resolves its target semantics. Later candidates run as bounded child features with their own research, ADR or amendment, plan, execution records, and review. A recurring audit refreshes the census; no plan remains open solely to symbolize continuing ownership.

The documentation lane separately aligns operator and developer material with the actual boundary: bindings are projections rather than attachments, secure business aggregates remain independently owned, foreign-asset rows are already connected, and stock inventory remains unconnected until a verified slice lands.

## Rationale

The ratcheted-census option is the only option that covers both present and future upstream disconnects while retaining falsifiable completion criteria. It composes with the accepted calculation aggregation decision, makes non-automation outcomes explicit, and prevents lexical similarity from becoming tax behavior. The research and two implementation references provide the grounding for the census boundary and vertical-slice contract.

## Consequences

- The project gains one auditable answer to which existing source capabilities are connected, blocked, intentionally manual, stale, or inapplicable.
- Inventory becomes the first adjudicated example without prejudging an unsafe `0155` or signed-value mapping.
- Deferred row families, fincas, assets, and future domains become visible through one classification vocabulary rather than ad hoc backlog prose.
- Every accepted connection carries source ownership, diagnostics, provenance, replay, encrypted persistence, and operator-path proof.
- Some apparently obvious automation candidates will remain manual or be rejected after tax adjudication.
- Continuous discovery produces recurring audit work and bounded child features rather than one perpetual plan, increasing lifecycle-document count while keeping each authorization honest.
- The census and gates require maintenance whenever a new secure domain, ingress surface, assembler, helper, source kind, or registry binding is introduced.
