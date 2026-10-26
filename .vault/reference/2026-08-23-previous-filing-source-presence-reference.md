---
tags:
  - '#reference'
  - '#previous-filing-source-presence'
date: '2026-08-23'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:46c1eb62758ed54c8b95eb982347f468350bb56005ffb8a9a333ca17ad911b66'
related: []
---

# `previous-filing-source-presence` reference: `Canonical previous-filing source presence`

This reference reconciles issue 113's M130 prior-year refusal against the
canonical Modelo 100 and Modelo 130 registries, the typed previous-filing
selector, resolver behavior, and focused calculation tests.

## Summary

The Modelo 100 registry already defines casillas 0224, 1479, 1553, and 1577. The schema is complete; parser fixtures are sample documents and must not define Modelo completeness.

That is registry functionality re-declared in Python.

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

All candidate ids remain in `source_casilla_ids` and continue through registry cross-model validation and observation requirements. Fixtures and tests do not own or mirror completeness. The existing hard-coded optionality helper must be deleted rather than supplemented.
