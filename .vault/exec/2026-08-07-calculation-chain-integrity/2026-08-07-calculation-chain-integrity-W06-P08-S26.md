---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:3c376dce0d6f717379f35b42c4a4d962068f960f431e47001142b3659f9d8777'
step_id: 'S26'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S26

## Outcome

Swept the observation-to-casilla routing surface by meaning. **A near-neighbour, proven NOT to cover the case** — the sharpest result of the three sweeps, because the naive dedup here would have destroyed data on a filing surface.

## What the sweep surfaced

`application/aggregation/_grouping.py:217` `fold_casilla_observations` is the canonical fold, consumed by four ledger projections: `_renta_income_ledger` (twice), `_renta_gasto_ledger`, `_irnr_income_ledger` and `_impatriado_income_ledger`.

A fifth site, `application/aggregation/_renta_ledger.py:793` `_casilla_aggregation`, builds the same `CasillaAggregation` by hand — same totals dict, same provenance rows, same construction — and does not call the canonical fold. On a name-and-shape reading it is an obvious fifth copy to retire.

## Why it is not promotable

Reading both, they differ in a way that matters and the canonical fold says so in its own contract:

> "Exactly one `CasillaProvenance` row is emitted per contributing casilla, in sorted casilla order, with `category_id` **unset** — this fold groups on the casilla axis alone."

`_casilla_aggregation` groups on `(target_casilla_id, category)` and emits a **populated** `category_id`, so it produces one provenance row per casilla-and-category pair.

Routing renta deductible expenses through the canonical fold would therefore collapse every per-category provenance row for a casilla into one row and blank its `category_id` — losing the breakdown of which spending categories contributed to a deductible total, on the surface that feeds filing evidence. The canonical fold's constraint shape is **narrower**, not a superset, so the substitutability pre-filter excludes this site.

## Disposition

Not actionable as a duplicate. Recorded as a constraint-shape divergence: two folds exist deliberately, one casilla-keyed and one casilla-and-category-keyed.

Worth noting for whoever revisits it: the honest unification is not "call the canonical fold" but "give the canonical fold an optional grouping key", and that is a larger change to a function four projections depend on. It is not free, and today's split costs nothing.
