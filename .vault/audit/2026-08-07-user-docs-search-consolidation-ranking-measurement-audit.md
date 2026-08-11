---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-07'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:acf7b878abf711d71f7bb744d522d43cfece046ac2f1fb8a50c0195cf3e0f47a'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# `user-docs-search-consolidation` audit: `Ranked-result measurement across modelo, casilla, natural-language and tax-term queries`

## Scope

Eight queries across the four classes the standing goal names - modelo, casilla, natural language, and tax term - driven through the shipped reader against the real built site: 2094 pages plus 8507 injected term, casilla, legal and CLI records, 90 of them relevance-boosted. The instrument is a headless browser loading the shipped controller, so the orderings below are what an operator sees, not a reconstruction of the comparator.

## Findings

### RANK-001 | FIXED | A legal provision no longer outranks the casilla and modelo cards it grounds

The legal record kind was aliased onto the user-documentation display class at three independent sites, so all 599 provisions carried the top band and outranked all 6377 casilla rows and every modelo card for every query. Corrected across the derivation, the per-kind projection, and the weight stamp.

Measured after the fix: for `estimacion directa simplificada` the four casilla cards precede the two legal articles, and for `recargo de equivalencia` the concept and regimen cards lead with the legal articles beneath them. Both orderings were inverted before.

### RANK-002 | OPEN | A per-query relevance boost is flattened to a global per-record weight, so one query's winner outranks everything everywhere

The committed relevance file is query-keyed: each mapping carries a query, a language, and its targets. The loader collapses it to `record_id -> strongest ranking_weight` across all queries, and the injector takes the stronger of that boost and the record's base weight, capped at 1. Pagefind stores one static weight per record, so the query dimension cannot survive into the index by this route.

The consequence is that any record which tops a single query is promoted globally. Measured: for the query `modelo 390` the Modelo 390 card carries 0.993754 and the presentation-deadline article carries 0.995524, against a legal base band of 0.75 - so the article leads. A sibling article in the same law, unboosted, sits at exactly 0.750000, which confirms the base band is correct and the boost is what escapes it.

This flattens the display-class ladder for the 90 boosted records; the ladder governs only the unboosted remainder. No decision record was found sanctioning cross-band boosting: the docstring states the intent as a floor ("ranks at least as high as its base tier"), which is not what taking the maximum produces.

### RANK-003 | OPEN | Natural-language queries recall no domain cards

The two natural-language probes returned two generic documentation pages each and no modelo, casilla, concept or legal card:

- `how do I file my quarterly VAT return` returned only a verify-a-draft page and a profile-setup page.
- `what happens if I file late` returned only an income-tax-year page and the same verify page.

The taxonomy classes do not share this weakness: modelo, casilla and tax-term queries all recall the right card kinds. The gap is specific to prose phrasing, which is the case the static semantic tier exists to serve, and that tier is dark - its coverage measures 0.748 against a 0.8 floor and its composed ladder scored worse than the lexical baseline, so enabling it would ship a regression.

### RANK-004 | OPEN | Prose queries fail on term conjunction, not on semantics

RANK-003 recorded that natural-language queries recall no domain cards. The cause is measurable and is mostly not semantic. Pagefind conjoins every query term, so one absent or rare term empties the result set. Removing only the function words, with no other change, restores recall by more than an order of magnitude:

| query | results |
|---|---|
| `how do I file my quarterly VAT return` | 2 |
| `quarterly VAT return` | 36 |
| `what happens if I file late` | 2 |
| `file late` | 41 |

The reader passes the raw query straight to Pagefind with no relaxation, so a reader who types a question rather than a keyword gets almost nothing.

A second, smaller cause is genuine vocabulary and morphology mismatch: `penalty late filing` returns 0 because the corpus says recargo and sancion, and the Spanish `presento` returns 0 while the corpus carries other forms of the same verb. Only this residue is what a semantic tier would answer.

**A corpus-frequency heuristic was tested as a language-agnostic way to drop function words, and it does not work.** Document frequency does not separate the two classes in this corpus: `my` matches 23 records while the content word `VAT` matches 180, and `quarterly` matches 1883 against `how` at 1862. Any relaxation must therefore be driven by an explicit per-language function-word authority or by progressive term relaxation, not by a frequency threshold. Recording the negative result so it is not re-attempted.

### RANK-005 | OPEN | Cross-lingual search fails on vocabulary coverage, not on the model or the ladder

The operator's requirement is that the same concept entered in any of the four languages returns the same results. The precompiled tier is built for exactly that -- a multilingual static embedding matrix, MIT-licensed, whose vocabulary already spans all four languages. Measured, the mechanism works and the data does not reach it.

Term labels across the 49 approved concepts: **es 49, en 17, ca 3, hu 3**. Exactly three concepts carry a term in all four languages, so three is the entire testable population, and that scarcity is itself the finding. Querying each language's term against the shipped matrix and the committed relevance mapping, with no model involved:

| concept | result |
|---|---|
| casilla | es/en/ca/hu return the same record set |
| prorrata-especial | es/en/ca/hu return the same record set |
| prorrata | es/en/ca agree; hu returns nothing |

The single failure is the corrupt Hungarian row described below. So cross-lingual retrieval succeeds wherever the vocabulary exists in the language, and the gap is authoring coverage rather than model quality, ladder composition or normalisation.

Directional only, measured against the locally cached model revision rather than the pinned one: description-level hu-to-es retrieval 57.1% top-1 and 77.6% top-5; en-to-es 71.4% and 91.8%. The es-to-es figure is an identity control and the ca-to-es figure is inflated by Catalan's lexical closeness to Spanish; neither is evidence about the tier.

**The tier should not ship in its current shape.** 114 vocabulary rows against 8,507 injected records means most queries never reach the matrix at all, which is why the composed ladder measured worse than the lexical baseline it would supplement. Enabling it would ship a regression. Making it real is an authoring programme of several hundred terms across four languages, with Catalan and Hungarian starting from three each -- not a code change. The honest alternatives are to fund that or to delete the tier and keep documentation search lexical.

### RANK-006 | FIXED | A corrupt Hungarian term embedded the wrong concept

The prorrata concept carried the Hungarian term `aranyositas`. That is not an accent-stripped spelling of `arányosítás` but a different word: `arány` is ratio, `arany` is gold, so the stored string meant gilding. Because a matrix row's vector is computed from the term string as written, that row encoded the wrong concept -- a silent retrieval fault rather than a display defect, and invisible to any check that only asks whether a term is present.

Corrected to `arányosítás`. Two consequences are recorded rather than resolved: the shipped matrix still carries the row compiled from the corrupt string, because a faithful recompile requires the pinned model revision which is absent from the local cache and whose deliberate fetch is an operator decision; and the committed relevance mapping still keys that entry by the old string. The mapping was deliberately NOT hand-edited, because its `dropped_count` is score-derived and a rename would fabricate provenance. The correct remediation is a re-sweep, which is itself blocked on the 39 Spanish scaffold placeholders recorded below.

### RANK-007 | OPEN | Scaffold placeholders block documentation generation, and recur

Generation of the casilla reference pages fails on missing source-locale labels. Measured registry-wide against the loaded authority, 19,558 casilla label keys resolve to **39 Spanish gaps -- 38 M390 intra-community acquisition rate tiers and one M303 continuidad key -- and every one is a self-referencing scaffold placeholder** rather than an absent key.

The placeholder stores the key as its own value, so it satisfies every existence and truthiness check while the resolver correctly refuses it. That is why the defect recurs unnoticed: running `scaffold` to declare keys without filling values produces a state that reads as present and behaves as missing. Three separate occurrences were observed and cleared during one session, and a fourth appeared within the hour.

Only the source locale gates generation, so the other three languages do not block. They are nonetheless far behind: of the same 19,558 keys, en is short 10,490, ca 10,324 and hu 10,525 -- roughly 46% covered against Spanish at 99.8%. Since the pages now deliberately render one language and refuse to fall back, a reader in those languages meets a hard failure rather than Spanish text across more than half the corpus. That is a consequence of doing the localization correctly and is currently unowned.

## Recommendations

RANK-002 wants a decision before code. Confining a boost to its class band is the shape that preserves both authorities - curation orders within a class, the ladder orders across classes - but simply clamping the boost to the base weight makes the feature inert, because a boost is then either below the base and ignored or above it and clipped back to it. A band with headroom, where a boosted record rises toward but never reaches the next band's floor, is the smallest design that keeps both. That is a ranking-contract change affecting 90 records and belongs in a decision record with a held-out measurement, not in an opportunistic edit.

RANK-003 is the standing goal's remaining substance. The lexical tier answers taxonomy queries well and prose queries poorly, and the semantic tier that would close it is correctly withheld. Raising its coverage past the floor is the work; enabling it as it stands is not.

RANK-001 needs no further action beyond the gates already landed, which assert the agreement between a record's stamped weight and the class it displays under rather than restating either table.

## 2026-08-11 disposition

Every finding above is now actioned. Recorded here so no item wears an open marker without a stated outcome.

**RANK-001, FIXED.** Unchanged, and now additionally gated: the pinned ladder enumerated only five of the six display classes, so the coverage assertion read `5 == 6` and the ordering assertion never saw the legal band at all. The legal class is enrolled in its ruled position and pinned from both sides, proven by restoring the original aliasing in memory.

**RANK-002, FIXED.** Closed under a decision record rather than an opportunistic edit, as this audit asked. A boost is now mapped into the band between its own class's declared weight and the next class's, with a reserved margin so it approaches but never reaches the class above. The band-with-headroom shape this audit recommended is the shape adopted; the clamp-to-base alternative was rejected for the inertness this audit predicted, and a strict within-band ordering assertion now catches exactly that failure mode. 55 of the 90 boosted records carried a raw weight at or above their band ceiling, so the flattening was systemic rather than a single outlier.

**RANK-003 and RANK-004, CARRIED FORWARD as lexical-tier work.** ADR Update 12 retires the semantic tier, so the prose-recall gap is explicitly not carried forward to it. This audit's own measurement is why that is honest rather than a downgrade: the dominant cause is term conjunction, not semantics, and removing function words alone restored recall by more than an order of magnitude. The remedy is an explicit per-language function-word authority or progressive term relaxation. The negative result on corpus-frequency thresholds stands as recorded and should not be re-attempted.

**RANK-005, RESOLVED as the retirement evidence.** This finding is the substance of the Rung-2 ruling. The operator ruled the tier's removal intended, and ADR Update 12 (D12) records the retirement citing these measurements. The multilingual authoring programme is a formally deferred carry-forward, not dropped scope.

**RANK-006, PARTIALLY CLOSED.** The corrupt Hungarian term is corrected in the Handbook. The committed relevance mapping still keys the stale string, and the target-vocabulary gate is red on it. The remediation remains the re-sweep this audit named, and the re-sweep is blocked: it needs the authoritative record projection, which currently refuses because a peer campaign's M303 casillas carry declared-but-null Spanish labels. Deliberately not hand-edited, for the reason this audit gave.

**RANK-007, RECURRED and RE-ATTRIBUTED.** The failure shape has changed. This audit recorded 39 self-referencing scaffold placeholders; at HEAD there are none, and the blocking shape is now a declared key with a null value, which `scaffold --check` reports as clean while the resolver correctly refuses it. 889 Spanish casilla labels are null, every one of them M303, landed by the active M303 registry buildout on 2026-08-10 and 2026-08-11. Spanish is the mandatory source locale, so the projection's hard refusal is correct and must not be softened into a skip. Owner is that campaign.
