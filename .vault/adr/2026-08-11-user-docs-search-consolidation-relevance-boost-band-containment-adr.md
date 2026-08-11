---
tags:
  - '#adr'
  - '#user-docs-search-consolidation'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:6cec552bdda0028491e2f834b3585712ed4bbc791e50a8a42df1f4d41eccb0e5'
related:
  - "[[2026-08-07-user-docs-search-consolidation-ranking-measurement-audit]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# `user-docs-search-consolidation` adr: `confine a per-query relevance boost to its display-class band` | (**status:** `accepted`)

## Problem Statement

The committed relevance file is query-keyed: each mapping carries a query, a language, and the record targets that query resolved to, each with its own `ranking_weight`. Pagefind, however, stores exactly one static weight per record. The query dimension cannot survive into the index by this route, and the loader resolves the mismatch by collapsing every mapping to `record_id -> strongest ranking_weight` across all queries. The injector then takes the stronger of that collapsed boost and the record's base weight, capped at 1.

The consequence is that a record which tops a single query is promoted for every query. The ranking measurement audit recorded it directly: for the query `modelo 390` the Modelo 390 card carries 0.993754 while the presentation-deadline article carries 0.995524, against a legal base band of 0.75, so the article leads. An unboosted sibling article in the same law sits at exactly 0.750000, which confirms the declared band is correct and that the boost is what escapes it.

This flattens the display-class ladder for the 90 boosted records. The ladder then governs only the unboosted remainder, which is not what either authority was designed to do: curation orders results *within* a class, and the ladder orders *across* classes. No decision record sanctioned cross-band promotion. The injector's own docstring states the intent as a floor -- a sweep-favoured record "ranks at least as high as its base tier" -- which is not what taking the maximum produces.

## Decision Drivers

- **Two authorities, two axes.** Curation knows that for `modelo 390` the presentation-deadline article is the most relevant *article*. It does not know, and must not decide, that an article outranks the modelo card. That second judgement belongs to the ratified ladder.
- **A clamp alone makes the feature inert.** Simply clamping the boost to the base weight leaves it either below the base and ignored, or above it and clipped back to it. Either way every boosted record collapses onto its band floor and curation stops ordering anything.
- **The declared table is ratified and should survive.** The ladder ordering, including the legal band's corrected position beneath the surfaces it grounds, was decided on measured evidence. A fix that re-derives every base weight would put that ratification back in play for no reason the defect requires.
- **Determinism.** The injected weight must be a pure function of the record's class and its committed boost, so two builds on two machines produce byte-identical indexes.

## Considered Options

- **O1, band with headroom: map the boost into the interval between the record's own band floor and the next band's floor, never reaching it. Chosen.**
- **O2, clamp the boost to the base weight.** Rejected: inert, as above.
- **O3, leave the boost global and accept cross-band promotion.** Rejected: it is the defect, and it silently disables the ladder for exactly the records curation cared most about.
- **O4, carry the query dimension into the index (per-query weights).** Rejected: Pagefind stores one static weight per record, so this requires either a parallel per-query index or a runtime re-rank against a shipped query-weight table. The first multiplies index size by the query count; the second is a new shipped data authority and a new client tier, which is a far larger change than the defect warrants.

## Decision

**R1 - The declared per-display-class weights become band FLOORS, unchanged in value and order.** `doc` 1.0, `modelo` 0.9, `casilla` 0.8, `legal` 0.75, `cli` 0.7, `technical` 0.5. Nothing about the ratified ladder is reopened.

**R2 - Each band's ceiling is the next-higher band's floor.** The top band's ceiling is 1.0. A band's headroom is its ceiling minus its floor.

**R3 - A boost orders within the band and never leaves it.** For a record whose display class has floor `f` and headroom `h`, and a committed boost `r` in `[0, 1]`, the injected weight is `f + r * h * RESERVE`, with `RESERVE` strictly less than 1 so the result is strictly below the ceiling. `RESERVE` is 0.9. A record with no committed boost keeps its existing weight untouched.

**R4 - The top band has zero headroom, and that is intended.** `doc` floors at 1.0, which is also the ceiling, so a boosted user-documentation record sits at 1.0 exactly. The top band needs no promotion: it is already first, and ordering within it falls to Pagefind's own lexical score, which is what unboosted records already rely on. This consequence is stated rather than engineered around, because raising the ceiling above 1.0 or lowering `doc` below it would reopen R1.

**R5 - Boosted outranks unboosted within a class, and the two anchors are different on purpose.** A boosted record anchors at its band floor and rises. An unboosted record keeps the weight the record funnel already gave it, which the existing sweep-score modulation may place at or below the floor. So within one class every boosted record ranks at or above every unboosted one, which is the ordering curation exists to express.

**R6 - The gate asserts the invariant, not the arithmetic.** The gate proves that no record's injected weight reaches its band's ceiling, computed over the real committed relevance data and the real declared table rather than over a synthetic fixture. Re-introducing the maximum must fail it. A gate that merely recomputed the formula and compared it to itself would prove nothing.

## Consequences

- The 90 boosted records stop escaping their bands. The `modelo 390` inversion the audit measured resolves: the article returns beneath the modelo card while staying ahead of unboosted articles.
- Curation keeps its authority and loses none of its resolution: within a band, boosts still order records continuously by strength.
- The measurement this change is judged on is the band invariant over the committed corpus, not the held-out miss rate. The miss rate measures whether a query recalls its target at all; it is insensitive to the order in which the recalled records are presented, so it cannot detect this defect and does not move when it is fixed. Stating that here prevents a future reader from reading an unchanged miss rate as evidence the fix did nothing.
- The relevance file's per-query structure is retained even though the index cannot carry it. It remains the reviewable provenance of why a record is boosted, and it is what a future per-query re-rank would need if O4 is ever revisited.
