---
tags:
  - '#reference'
  - '#previous-filing-source-presence'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:9fc147c14e5d93aaace536c9f0e58b81fbd5cb46d50752badece3875c76908c8'
related: []
---

# `previous-filing-source-presence` reference: `Canonical previous-filing source presence`

This reference reconciles issue 113's M130 prior-year refusal against the
canonical Modelo 100 and Modelo 130 registries, the typed previous-filing
selector, resolver behavior, and focused calculation tests.

## Summary

The Modelo 100 registry already defines casillas 0224, 1479, 1553, and 1577.
The Modelo 130 binding in
`src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/bindings/0002-bindings.toml:4`
selects those canonical casillas, while its official source citation says
"0224, 1479, 1553 y/o 1577". The schema is complete; parser fixtures are sample
documents and must not define Modelo completeness.

The divergence is in
`src/cadrumo/domain/calculations/registry/_bindings_previous_filing.py:161`.
`_optional_source_casilla_ids` infers presence policy from the aggregation op
and tuple position, making the second `prior_pagos_fraccionados` source optional
while treating every other plural source as mandatory. That is registry
functionality re-declared in Python.

The canonical repair is one typed selector field:
`required_source_casilla_ids`. When omitted, every candidate source casilla is
required, preserving strict behavior. An explicit empty tuple permits any
candidate subset but still requires at least one candidate to be observed. The
M130 annual binding declares an empty required set; the prior-payment binding
declares only casilla 07 required, allowing absent casilla 16. Missing optional
sources contribute the aggregation identity zero. Missing required sources, or
a matched observation containing none of the declared candidates, fail closed.

When bindings share one source filing coordinate, each optional-any binding
contributes its own `source_presence_groups` row. The coalesced typed
requirement therefore retains "at least one from each binding" rather than
weakening it to "at least one from the union". The canonical
`source_presence_gaps` primitive enforces the derived groups for live capture
and cross-period clean-state evaluation.

All candidate ids remain in `source_casilla_ids` and continue through registry
cross-model validation and observation requirements. Fixtures and tests do not
own or mirror completeness. The incorrect test in
`src/cadrumo/application/calculations/tests/test_previous_filing_absence_versus_malformed.py:85`
must be replaced by separate proofs that one applicable M100 casilla resolves
and that zero applicable casillas refuse. The existing hard-coded optionality
helper must be deleted rather than supplemented.
