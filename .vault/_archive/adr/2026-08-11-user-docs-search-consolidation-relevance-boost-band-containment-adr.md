---
tags:
  - '#adr'
  - '#user-docs-search-consolidation'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:9b4c15b91a4a99393f5509b656e08c10980cddfb66f5939652921037fc519bd0'
related:
  - "[[2026-08-07-user-docs-search-consolidation-ranking-measurement-audit]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# `user-docs-search-consolidation` adr: `confine a per-query relevance boost to its display-class band` | (**status:** `accepted`)

## Problem Statement

The committed relevance file is query-keyed: each mapping carries a query, a language, and the record targets that query resolved to, each with its own `ranking_weight`. The search index, however, stores exactly one static weight per record. The query dimension cannot survive into the index by this route, and the loader resolves the mismatch by collapsing every mapping to one strongest weight per record across all queries. The injector then takes the stronger of that collapsed boost and the record's base weight, capped at 1.

The consequence is that a record which tops a single query is promoted for every query. This flattens the display-class ladder for the boosted records, leaving the ladder to govern only the unboosted remainder. That is not what either authority was designed to do: curation orders results within a class, and the ladder orders classes against each other. No decision record sanctioned cross-band promotion, and the injector's own docstring stated the intent as a floor, which is not what taking the maximum produces.

## Considerations

- The defect is measured, not inferred: `2026-08-07-user-docs-search-consolidation-ranking-measurement-audit` finding RANK-002 recorded a legal provision at 0.995524 leading the modelo card at 0.993754 for the query `modelo 390`, against a legal base band of 0.75, with an unboosted sibling article at exactly 0.750000 confirming the band itself is correct.
- The scale is systemic, not anecdotal: of 90 distinct boosted records in the committed corpus, 55 carry a raw weight at or above their own band's ceiling.
- Curation and the ladder encode different knowledge. Curation knows which article is most relevant for a query; it does not know, and must not decide, that an article outranks the modelo card it grounds.
- The declared ladder was itself ratified on measured evidence, including the legal band's corrected position under RANK-001. A fix that re-derives every base weight would reopen that ratification for no reason the defect requires.
- The injected weight must be a pure function of the record's class and its committed boost, so two builds produce byte-identical indexes.

## Considered options

- **O1, band with headroom: map the boost into the interval between the record's own band floor and the next band's floor, never reaching it. Chosen.** Preserves both authorities on their own axes; costs one derived ceiling per class.
- **O2, clamp the boost to the base weight.** Rejected: inert. The boost is then either below the base and ignored, or above it and clipped back to it, so distinct boosts collapse onto the band floor and curation stops ordering anything.
- **O3, leave the boost global and accept cross-band promotion.** Rejected: it is the defect, and it silently disables the ladder for exactly the records curation cared most about.
- **O4, carry the query dimension into the index as per-query weights.** Rejected: the index stores one static weight per record, so this needs either a parallel index per query or a runtime re-rank against a shipped query-weight table. The first multiplies index size by the query count; the second adds a new shipped data authority and a new client tier, far exceeding what the defect warrants.

## Constraints

- The one static weight per record is a property of the search engine, not of this project's code, so no arrangement of the committed data can make the query dimension survive injection. Every option except O4 accepts that; O4 pays for it with a new shipped artefact.
- The declared per-class weight table is treated as fixed. It is normalised so the top class sits at the scale's ceiling, which means the top class has no headroom and boosts cannot order within it. This is a real limitation of working inside the ratified table rather than re-deriving it.
- The held-out miss-rate instrument cannot measure this change. It measures whether a query recalls its target at all and is insensitive to presentation order, so it neither detects the defect nor moves when it is fixed.
- No frontier dependency: the change is arithmetic over an existing declared table, with no new library, service or model.

## Implementation

The declared per-display-class weights become band floors, unchanged in value and order. Each band's ceiling is the next-higher class's floor, derived by sorting the one declared table so a reordered or extended table cannot leave a stale hand-listed bound behind; the top band's ceiling is the scale's ceiling. A band's headroom is its ceiling minus its floor.

A containment function maps a committed boost into its class's band: the floor plus the clamped boost scaled by the headroom and a reserve fraction strictly below 1, so a full boost approaches the ceiling without reaching it. A zero boost yields the floor exactly, which is what preserves the ladder. The injector's effective-weight seam calls that function with the record's derived display class; a record the relevance file does not name keeps the weight the record funnel gave it, so within a class every boosted record ranks at or above every unboosted one.

The gate asserts the invariant over the real committed relevance data and the real declared table, never a synthetic fixture, and is preceded by an anchor asserting the corpus actually contains boosts that would escape, so a future corpus with nothing to contain cannot let it pass vacuously.

## Rationale

O1 wins on the knockout criterion the audit itself identified: it is the only option that keeps both authorities. O3 keeps curation and destroys the ladder. O2 keeps the ladder and makes curation inert. O4 keeps both but pays a shipped-artefact and client-tier cost out of all proportion to a ranking defect, and would reopen the runtime boundary this feature has repeatedly closed.

Deriving ceilings from the declared table rather than listing them is what makes the fix survive its own maintenance: the same class of staleness put a five-entry ladder against a six-member enum and let the legal band go unchecked entirely.

The top band's lack of headroom is accepted rather than engineered around. Raising the ceiling or lowering that class's floor would put the ratified table back in play, and the top class needs no promotion: it is already first, and ordering within it falls to the engine's own lexical score, which is what unboosted records already rely on.

## Consequences

- The boosted records stop escaping their bands. The measured inversion resolves: the article returns beneath the modelo card while staying ahead of unboosted articles.
- Curation keeps its authority and its resolution: within a band, boosts still order records continuously by strength.
- The evidence for this change is the band invariant over the committed corpus, not the held-out miss rate. Stating that here prevents a future reader from reading an unchanged miss rate as evidence the fix did nothing.
- Boosted user-documentation records tie at the top band's ceiling and are ordered only by the engine's lexical score. If within-class ordering is later wanted there, it requires re-deriving the declared table, which is a separate decision.
- The relevance file keeps its per-query structure even though the index cannot carry it. It remains the reviewable provenance of why a record is boosted, and it is what O4 would need if that option is ever revisited.
