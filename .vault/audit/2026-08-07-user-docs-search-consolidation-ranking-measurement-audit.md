---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:c74cd5652fe39870dbc28d89b30f8adc1902c9bf5d05daf11afab1d8af272bd0'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace user-docs-search-consolidation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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

## Recommendations

RANK-002 wants a decision before code. Confining a boost to its class band is the shape that preserves both authorities - curation orders within a class, the ladder orders across classes - but simply clamping the boost to the base weight makes the feature inert, because a boost is then either below the base and ignored or above it and clipped back to it. A band with headroom, where a boosted record rises toward but never reaches the next band's floor, is the smallest design that keeps both. That is a ranking-contract change affecting 90 records and belongs in a decision record with a held-out measurement, not in an opportunistic edit.

RANK-003 is the standing goal's remaining substance. The lexical tier answers taxonomy queries well and prose queries poorly, and the semantic tier that would close it is correctly withheld. Raising its coverage past the floor is the work; enabling it as it stands is not.

RANK-001 needs no further action beyond the gates already landed, which assert the agreement between a record's stamped weight and the class it displays under rather than restating either table.
