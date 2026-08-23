---
tags:
  - '#adr'
  - '#inventory-casilla-mapping'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:ba19491912e0bb98653add8781baf31385663a72f5cce0112b0d704ad0702cbd'
related:
  - "[[2026-08-23-inventory-casilla-grounding-research]]"
  - "[[2026-08-22-source-casilla-integration-adr]]"
  - '[[2026-07-05-modelo-720-row-carrier-adr]]'
---

# `inventory-casilla-mapping` adr: `2025 Modelo 100 inventory acquisition cost and split stock variation` | (**status:** `accepted`)

## Problem Statement

The inventory domain has the correct activity-scoped ledger boundary but does not yet expose a legally complete, source-owned projection for Modelo 100 inventory casillas. The current signed helper and purchase subtotal cannot be bound safely. A registry selector containing one literal activity ID also cannot represent the taxpayer's runtime set of encrypted inventory ledgers. This decision defines the supported revision, output identities, source completeness, authority, absence, override, and typed runtime activity-row contracts for the first inventory connection grounded by `2026-08-23-inventory-casilla-grounding-research`.

## Considerations

- The connection must extend the accepted resolver, registry, provenance, secure-persistence, and connectivity-proof architecture rather than create a parallel calculation path; `2026-08-22-source-casilla-integration-adr`.
- Casilla meaning, sign, grain, source authority, absence behavior, and override policy must be explicit before a source becomes connected; `2026-08-22-modelo-work-binding-architecture-inventory-gap-verification-reference`.
- The current inventory purchase value is not a complete acquisition-cost fact, and the current signed variation helper does not represent the official output shape; `2026-08-23-inventory-casilla-grounding-research`.
- The supported legal slice is ejercicio 2025 only; repeated identifiers in other revisions do not authorize continuity; `2026-08-23-inventory-casilla-grounding-research`.
- Immutable registry declarations cannot know taxpayer-specific activity identities, while the accepted source mesh already carries row-indexed binding values and established M303, M349, and M720 precedents preserve runtime row identity; `2026-08-23-inventory-casilla-grounding-research` and `2026-07-05-modelo-720-row-carrier-adr`.

## Considered options

### Bind the existing purchase subtotal and signed variation helper

This minimizes source changes but permits an incomplete acquisition-cost declaration, collapses two mutually exclusive outputs, and preserves a stale casilla identity. Rejected.

### Keep all three casillas manual

This avoids unsafe automation but leaves a source domain with sufficient grain and valuation capability disconnected even after its missing semantics can be made explicit. Rejected as the permanent design, while remaining the fallback when no authoritative source is connected.

### Expose one complete inventory projection with three source-owned outputs

Correct the inventory source semantics first, then resolve acquisition cost and the two sign-split variation values as one typed, provenance-bearing projection at taxpayer, year, and activity grain. Kept only with typed runtime activity-row expansion; a static activity selector is rejected.

### Declare one literal registry binding set per activity or use a wildcard aggregate

Literal declarations fabricate taxpayer-specific identities in immutable shared authority. A wildcard followed by a taxpayer-wide sum erases the official per-activity grain. Rejected.

### Expand immutable operation templates over encrypted runtime activity rows

Let the registry own the three operation-to-casilla row-template semantics and let the encrypted ledger supply the canonical activity instances. Carry the expanded values through the existing structured row-indexed binding channel. Accepted.

## Constraints

- The initial mapping is limited to Modelo 100 ejercicio 2025. Earlier or later revisions require separately grounded authority.
- Resolution grain is exactly one taxpayer, filing year, and economic activity. Values must not be combined across activities before the registry-authorized filing aggregation stage.
- The immutable registry owns operation, destination casilla, legal/source grounding, revision scope, and row-template semantics. It must not contain a taxpayer activity ID, wildcard, or fabricated static activity roster.
- The encrypted runtime inventory ledger is the sole source of canonical `actividad_id` instances. Expansion must be deterministic, preserve exact activity identity and provenance, and refuse duplicate or ambiguous activity rows.
- Source resolution carries each expanded operation value as a structured row-indexed binding coordinate compatible with `CalculationSourceResolution.row_binding_values`; a binding ID remains a real registry ID and the 1-based row index remains a separate typed coordinate.
- Row indexes are transport/projection coordinates, not replacement activity identities. Replay and review must preserve the association between each row coordinate and its canonical `actividad_id`.
- Inventory row values do not enter the scalar formula engine or taxpayer-wide aggregation merely because they use the row carrier. Any scalar formula consumption or cross-activity fold requires an explicit separately adjudicated registry aggregation contract.
- Casilla `0181` is complete acquisition cost: purchase consideration plus directly attributable acquisition costs and non-recoverable IVA, excluding recoverable IVA. The current IVA-exclusive subtotal is never an acceptable substitute.
- Inventory source semantics must represent and validate that complete acquisition cost before `0181` is connected. A binding must not compensate for an incomplete source fact.
- Casilla `0177` is `max(closing - opening, 0)` and casilla `0182` is `max(opening - closing, 0)`. They are mutually exclusive for a source projection; both may be zero.
- An explicit physical closing valuation may be authoritative only when its provenance identifies the observation and valuation basis, continuity against the prior authoritative closing is checked, and any conflict with movement-derived closing is retained as an actionable diagnostic. An unexplained override is not authoritative.
- Missing, incomplete, inconsistent, conflicting without adjudicated authority, or unreadable source state fails closed. It leaves the source outputs unresolved with actionable diagnostics and never supplies inferred zeroes.
- The accepted source-casilla integration and calculation aggregation contracts are stable parent features. The inventory acquisition-cost and explicit-closing write semantics are not yet sufficient and are blocking prerequisites for source readiness.

## Implementation

Replace the stale `0155` inventory helper with a typed 2025 inventory activity-row projection that produces `0181`, `0177`, and `0182` for each taxpayer-year-activity coordinate. No compatibility alias or alternate signed-output path remains.

Author one immutable registry row-template family for the three inventory operations and their exact destination casillas. At resolution time, enumerate the canonical activity rows from the encrypted inventory document, order them deterministically, and expand every applicable operation template over each row. The registry declaration carries no literal `actividad_id`; the runtime row carries that identity alongside its source provenance and projection fingerprint.

Emit expanded values through the source mesh's row-indexed binding-value channel using the unchanged registry `BindingId` plus a 1-based row index. Preserve the row-to-`actividad_id` association in the source/revision review state so reordering or substitution cannot change meaning silently. Collision checks operate on the full structured coordinate and activity identity; no synthetic binding IDs, wildcard selectors, or taxpayer-wide sum path is introduced.

Correct the canonical inventory source model so each acquisition can prove its complete acquisition cost, including attributable costs and the recoverability treatment of IVA. Only after that source fact is validated may the resolver emit `0181`.

Resolve opening and closing through the canonical inventory valuation path. A provenance-complete physical closing may supersede the derived closing under the authority conditions above; otherwise the derived valuation remains authoritative or resolution refuses. Emit continuity and closing-conflict diagnostics without discarding the competing observations.

Enroll the projection through the existing registry binding, resolver mesh, provenance graph, encrypted calculation revision, connectivity proof, and operator paths. A complete authoritative ledger owns all three outputs and refuses caller replacement. When no complete authoritative ledger is connected, the casillas remain unresolved and deliberate manual input may be used through the existing manual path; manual input does not masquerade as inventory-source resolution.

Validation enforces revision scope, coordinate identity, acquisition-cost completeness, mutual exclusion, continuity, source readability, provenance, collision refusal, and calculate/pull parity.

## Rationale

The complete three-output runtime-row projection is the only option that preserves both official activity grain and immutable registry authority while preventing under-declaration and false zeroes. It uses the already accepted row carrier rather than inventing taxpayer facts in TOML or a new inventory-only envelope, makes the source ledger authoritative only when its facts are complete and reviewable, and removes the misleading signed helper instead of institutionalizing it as a compatibility surface. The governing choices are grounded by `2026-08-23-inventory-casilla-grounding-research`, compose with `2026-08-22-source-casilla-integration-adr`, and follow the carrier boundary of `2026-07-05-modelo-720-row-carrier-adr`.

## Consequences

- Modelo 100 ejercicio 2025 gains one auditable inventory source contract at the correct activity grain.
- One registry template family can serve any valid runtime activity roster without static IDs, wildcards, or synthetic binding identifiers.
- Calculation revisions and review surfaces must preserve row-to-activity identity in addition to row-indexed binding values, increasing the strict replay and mutation-test surface.
- The scalar formula engine remains unchanged; inventory row folding stays refused until an explicit aggregation decision exists.
- Positive and negative stock variation cannot populate both income and expense outputs for the same projection.
- Acquisition-cost enrichment is mandatory before `0181` can become source-backed, so implementation cannot ship by forwarding the existing subtotal.
- Physical closing observations can become authoritative without silently erasing derived valuation or continuity conflicts.
- Complete source state prevents caller overrides; absent or defective state remains visibly unresolved and preserves manual fallback.
- The stale inventory meaning attached to `0155` disappears with no compatibility path.
- Supporting earlier revisions, production-cost composition, or new valuation authorities requires further grounding and decision work.

