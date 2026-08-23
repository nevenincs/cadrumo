---
tags:
  - '#adr'
  - '#inventory-casilla-mapping'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:0dd018890991e8d534ffc89d4e0b57c67cc78809a59e7712be7056535a86fe46'
related:
  - "[[2026-08-23-inventory-casilla-grounding-research]]"
  - "[[2026-08-22-source-casilla-integration-adr]]"
---

# `inventory-casilla-mapping` adr: `2025 Modelo 100 inventory acquisition cost and split stock variation` | (**status:** `accepted`)

## Problem Statement

The inventory domain has the correct activity-scoped ledger boundary but does not yet expose a legally complete, source-owned projection for Modelo 100 inventory casillas. The current signed helper and purchase subtotal cannot be bound safely. This decision defines the supported revision, output identities, source completeness, authority, absence, and override contracts for the first inventory connection grounded by `2026-08-23-inventory-casilla-grounding-research`.

## Considerations

- The connection must extend the accepted resolver, registry, provenance, secure-persistence, and connectivity-proof architecture rather than create a parallel calculation path; `2026-08-22-source-casilla-integration-adr`.
- Casilla meaning, sign, grain, source authority, absence behavior, and override policy must be explicit before a source becomes connected; `2026-08-22-modelo-work-binding-architecture-inventory-gap-verification-reference`.
- The current inventory purchase value is not a complete acquisition-cost fact, and the current signed variation helper does not represent the official output shape; `2026-08-23-inventory-casilla-grounding-research`.
- The supported legal slice is ejercicio 2025 only; repeated identifiers in other revisions do not authorize continuity; `2026-08-23-inventory-casilla-grounding-research`.

## Considered options

### Bind the existing purchase subtotal and signed variation helper

This minimizes source changes but permits an incomplete acquisition-cost declaration, collapses two mutually exclusive outputs, and preserves a stale casilla identity. Rejected.

### Keep all three casillas manual

This avoids unsafe automation but leaves a source domain with sufficient grain and valuation capability disconnected even after its missing semantics can be made explicit. Rejected as the permanent design, while remaining the fallback when no authoritative source is connected.

### Expose one complete inventory projection with three source-owned outputs

Correct the inventory source semantics first, then resolve acquisition cost and the two sign-split variation values as one typed, provenance-bearing projection at taxpayer, year, and activity grain. Accepted.

## Constraints

- The initial mapping is limited to Modelo 100 ejercicio 2025. Earlier or later revisions require separately grounded authority.
- Resolution grain is exactly one taxpayer, filing year, and economic activity. Values must not be combined across activities before the registry-authorized filing aggregation stage.
- Casilla `0181` is complete acquisition cost: purchase consideration plus directly attributable acquisition costs and non-recoverable IVA, excluding recoverable IVA. The current IVA-exclusive subtotal is never an acceptable substitute.
- Inventory source semantics must represent and validate that complete acquisition cost before `0181` is connected. A binding must not compensate for an incomplete source fact.
- Casilla `0177` is `max(closing - opening, 0)` and casilla `0182` is `max(opening - closing, 0)`. They are mutually exclusive for a source projection; both may be zero.
- An explicit physical closing valuation may be authoritative only when its provenance identifies the observation and valuation basis, continuity against the prior authoritative closing is checked, and any conflict with movement-derived closing is retained as an actionable diagnostic. An unexplained override is not authoritative.
- Missing, incomplete, inconsistent, conflicting without adjudicated authority, or unreadable source state fails closed. It leaves the source outputs unresolved with actionable diagnostics and never supplies inferred zeroes.
- The accepted source-casilla integration and calculation aggregation contracts are stable parent features. The inventory acquisition-cost and explicit-closing write semantics are not yet sufficient and are blocking prerequisites for source readiness.

## Implementation

Replace the stale `0155` inventory helper with a typed 2025 inventory projection that produces `0181`, `0177`, and `0182` for one taxpayer-year-activity coordinate. No compatibility alias or alternate signed-output path remains.

Correct the canonical inventory source model so each acquisition can prove its complete acquisition cost, including attributable costs and the recoverability treatment of IVA. Only after that source fact is validated may the resolver emit `0181`.

Resolve opening and closing through the canonical inventory valuation path. A provenance-complete physical closing may supersede the derived closing under the authority conditions above; otherwise the derived valuation remains authoritative or resolution refuses. Emit continuity and closing-conflict diagnostics without discarding the competing observations.

Enroll the projection through the existing registry binding, resolver mesh, provenance graph, encrypted calculation revision, connectivity proof, and operator paths. A complete authoritative ledger owns all three outputs and refuses caller replacement. When no complete authoritative ledger is connected, the casillas remain unresolved and deliberate manual input may be used through the existing manual path; manual input does not masquerade as inventory-source resolution.

Validation enforces revision scope, coordinate identity, acquisition-cost completeness, mutual exclusion, continuity, source readability, provenance, collision refusal, and calculate/pull parity.

## Rationale

The complete three-output projection is the only option that preserves the official presentation identities while preventing under-declaration and false zeroes. It uses the existing source-integration architecture, makes the source ledger authoritative only when its facts are complete and reviewable, and removes the misleading signed helper instead of institutionalizing it as a compatibility surface. The governing choices are grounded by `2026-08-23-inventory-casilla-grounding-research` and compose with `2026-08-22-source-casilla-integration-adr`.

## Consequences

- Modelo 100 ejercicio 2025 gains one auditable inventory source contract at the correct activity grain.
- Positive and negative stock variation cannot populate both income and expense outputs for the same projection.
- Acquisition-cost enrichment is mandatory before `0181` can become source-backed, so implementation cannot ship by forwarding the existing subtotal.
- Physical closing observations can become authoritative without silently erasing derived valuation or continuity conflicts.
- Complete source state prevents caller overrides; absent or defective state remains visibly unresolved and preserves manual fallback.
- The stale inventory meaning attached to `0155` disappears with no compatibility path.
- Supporting earlier revisions, production-cost composition, or new valuation authorities requires further grounding and decision work.
