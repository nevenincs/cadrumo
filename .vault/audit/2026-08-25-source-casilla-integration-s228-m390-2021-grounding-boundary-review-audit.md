---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:3bb1f197f0aa6aa8feef95b75d2907ad7a19e30b33a93dfd5dfae34e03233db4'
related: []
---

# `source-casilla-integration` audit: `S228 M390 2021 grounding-boundary review`

## Scope

Independent review of mixed implementation `fb86bf5a2e` and completion
`0a3478a702`: primary 2021 evidence, complete annual surface versus the ten
parser casillas, filed-observation and later-route limits, the model-scoped ADR,
and the no-runtime/no-census boundary.

## Findings

### source evidence and temporal boundary | low | exact 2021 scope is grounded

The bundled official 2021 design recomputes to SHA-256
`0164fbea6f500a63950b762f5b5e43c5d771f84ac8d260e70dc1497acaed4246`.
The registry selects only `390/2021/0A` and calls it applicability-grade. Its
ten declared casillas and PDF extractor are observation-only; they do not
represent the official annual record''s identity, repeated-row, regime,
territory, sign, unit, or absent-value semantics.

### decision boundary | low | ADR is sole model-specific normative home

The accepted M390-2021 ADR alone makes the `grounding_blocked` decision and
requires a complete semantic map, encrypted source owners, exact revision,
lifecycle/replay/review, and separate layout/serializer proof to reopen.
The framework ADR remains the generic authority. Exact ADR review confirms that
the historical autoconsumo and carry-box records address later, narrow M390
calculation routes and do not duplicate or authorize the 2021 refusal.

### no promotion | low | existing evidence remains non-substitutable

The filed-declaration store is read-only historical observation evidence; it
does not create a pre-filing owner. Later M390 resolvers and exporter routes
remain revision-bound and cannot be projected back to 2021. Both reviewed
commits alter Vault documentation only: no source-connectivity census row,
source taxonomy, binding, resolver, producer, lifecycle, registry, layout, or
export claim was added.

### verification | low | focused gates support the decision boundary

Ruff passed on those focused test paths. Vault structural, frontmatter, links, schema, and ADR-status checks are clean. Remaining Vault warnings are pre-existing feature annotations and concurrent unrelated work.

## Recommendations

PASS. Retain the bounded `grounding_blocked` disposition. Reopen only through
an accepted 2021 vertical slice satisfying every ADR predicate limb; neither
parser coordinates, a filed declaration, manual entry, nor later M390 routes
are substitutes.
