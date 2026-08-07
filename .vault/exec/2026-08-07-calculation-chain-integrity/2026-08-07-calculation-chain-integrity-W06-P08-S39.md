---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:7e041ab1c61e92546ab55119b212a030a148410dc0ba02c9724413188d355c6a'
step_id: 'S39'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S39

## Outcome

The both-sites enumeration exists and is correct: `_cross_modelo_source` in `test_reconciliation_pair_category_parity.py`, landed by `1c0bcf6428`. Verified at HEAD.

## The blind spot this Step names, confirmed

The function reads both declaration sites and says why in its own docstring:

> Querying only the relation site returns four pairs where five exist: the grupo pair (M353 against M322) is declared as a `previous_filing` binding carrying a cross-modelo `source_modelo`, never as a relation. A gate built on the relation list alone would pass over that pair permanently -- which is the same blind spot that let the M390 divergence ship.

So the enumeration walks `revision.relations` for `annual_summary` kinds AND `revision.bindings` for `previous_filing` bindings whose selector grouping is `per_grupo_member`, unioning the counterpart modelo ids.

## The narrowing is semantic, not an id list

Worth recording because it is the part most likely to be "simplified" later. Not every cross-modelo dependency is a reconciliation: `cross_model_output` carries one value into another modelo's calculation (M100 folding in an M130 pago fraccionado) and the two sides are never asserted equal. Only a periodic-to-annual summary and a grupo member-to-aggregate rollup claim the sides agree, which is what makes category parity meaningful for them.

Narrowing by declared semantics rather than by an id list is what stops the gate rotting when a sixth pair appears — it will be enumerated automatically if it declares either shape, and correctly ignored if it declares neither.

## Cross-reference

This is the enumeration `W02.P03.S40`'s gate consumes; the two Steps are one mechanism recorded from its two ends. The `test_reconciliation_pair_derivation_is_not_vacuous` guard is what keeps this enumeration honest: a derivation returning zero pairs would make the parity gate pass trivially, so the enumeration is asserted non-empty rather than trusted.
