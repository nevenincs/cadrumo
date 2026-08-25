---
tags:
  - '#research'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:2b18baffdb436b70a5ded49a460ae8e276f1d77ffe4453cca6286b81f333bfbd'
related:
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-07-13-docs-terminology-search-research]]"
---

# `user-docs-search-consolidation` research: `Deterministic casilla enrollment research`

The registry is already capable of deterministically projecting a casilla such as
Modelo 130 / casilla 15; the apparent non-enrollment is a measurement and delivery
boundary, not evidence that the schema row is unknown. The existing `casilla` coverage
number measures only sparse inbound RAG relevance references. It does not measure
registry projection, exact-address metadata, localized definition completeness, or a
generated Pagefind artifact. The evidence therefore supports treating those as separate
contracts, with an exact structured lookup for stable addresses and RAG for vocabulary
matching. The generated-site and post-resolver sweep proofs remain unverified because
tests, builds, live probes, and deployment were intentionally deferred.

## Findings

### Registry projection is deterministic, but projection is not the whole search contract

The casilla projection walks every validated registry casilla and deduplicates by
`(modelo, casilla.id)`, so the schema is the correct authority for the enumerable
casilla universe. `CasillaSearchRecord` then retains the canonical modelo and casilla
identity together with source and legal provenance. The unified record deliberately
keeps the opaque search id separate from those typed fields: consumers must match
`metadata.modelo` and `metadata.casilla_id`, not parse a search id. This means that a
registry row can be enrolled in the deterministic projection while still being absent
from a sparse relevance map or an unbuilt browser artifact.

The direct-schema intuition is therefore correct but incomplete: it guarantees that a
record can be derived; it does not itself materialize localized card text into each
language index, prove that the destination URL exists in the generated site, or create
a semantic mapping from arbitrary taxpayer language to that record.

### Definition data is a separate projection contract

The casilla search record now carries registry-backed localized help, data type, input
kind, requiredness, binding id, and formula id. The unified search metadata carries
the same typed fields, while intentionally omitting a formula expression because the
search projection does not own the revision formula table. The registry detail query
already resolves that richer formula expression when a caller asks for one exact
casilla. This separates “the search result explains what the field is” from “the
calculation registry can answer the full detailed report”; neither path should invent
definition text or a formula target.

Localization is likewise a content-surface property, not an enrollment predicate. A
record may have the canonical Spanish label and no authored non-Spanish help or label.
The census therefore distinguishes Spanish definition presence from non-Spanish locale
presence instead of treating one localized string as proof that every language is
complete.

### The old 22/6,359 figure is relevance coverage, not casilla enrollment

The existing coverage report joins the committed sweep's target record ids against the
derivable corpus. Its current artifact reports 6,359 casilla ids and 22 with an inbound
relevance reference. That is a useful measure of how much the sparse semantic map
currently reaches, but it cannot answer whether Modelo 130 / casilla 15 was projected,
has a target, has a definition, or was written to Pagefind. The new deterministic
casilla census exposes five axes—projected, exact target, definition, locale, and
relevance—so a future report can identify the failing seam rather than collapse all
failures into “not enrolled.”

This also explains why all-to-all RAG enrollment is not the right repair. It would make
the relevance denominator look healthier by assigning every field semantic neighbors,
but it would blur exact navigation and create noise for legal and calculation-related
queries. The evidence favors an exhaustive deterministic record/index surface plus a
reviewed sparse RAG map layered on top. Rung 2 vector or client-cosine work remains a
separate decision and is not required for an exact Modelo/casilla address.

### Exact structured search must bypass semantic ambiguity

The browser search controller now recognizes structured forms such as `modelo 130
casilla 15`, filters to `kind=casilla`, and matches normalized modelo, number, and
optional segmento metadata before falling back to the existing Pagefind ladder. The
canonical result target comes from the unified casilla record. This is the intended
stable path: the user’s explicit address is resolved against typed registry-derived
metadata, not guessed from a semantic score.

The path is not yet proven end to end. Pagefind filter/data behavior, the generated
language index, and the destination page still need the real-behaviour gate in P06.S24.
Until that gate and a fresh artifact check run, “implemented in source” must not be
reported as “searchable in the shipped site.”

### RAG hits must identify an individual casilla or fail closed

The prior resolver could receive a file-level casilla hit and select the first projected
record for that modelo. That was not deterministic enrollment; it was an arbitrary
fallback that could attach a taxpayer query to the wrong field. The resolver now
requires a TOML source path and a line range that overlaps exactly one casilla section,
then resolves exactly one projected record. Non-TOML hits, unreadable source ranges,
zero matches, and multi-section overlaps are dropped with a typed reason.

This is safer for relevance, but it changes the current sweep boundary: the committed
112-query relevance artifact was produced before this stricter resolver landed. A fresh
RAG sweep and coverage comparison are required before interpreting new relevance counts
or closing the semantic-enrollment steps.

### Current remediation boundary

The implementation work has landed in four focused commits: a deterministic coverage
census (`088e3255a8`), registry definition metadata propagation (`77c2e8ea49`),
fail-closed casilla resolution (`18a777cc44`), and the structured browser lookup
(`a4281864a9e31438ccc9b536657cb89d7576020f`). P06.S20–P06.S23 have execution records
and remain open in the plan pending review and acceptance. P06.S24 is the closing gate:
it must prove the five census surfaces, Modelo 130 / casilla 15 exact resolution,
projection/detail parity, localized definition expectations, and target resolvability.
Only then can the plan distinguish a missing registry projection from a missing build
artifact or an intentionally sparse semantic mapping.

Not investigated in this record: a new Pagefind build, browser execution against the
generated site, a post-change live RAG sweep, deployment roots, or the deferred test
suite. Those are explicit later verification boundaries, not passing results.

## Sources

- `dev/docs/terminology/_casilla_projection.py:82-105`
- `dev/docs/terminology/_casilla_projection.py:190-202`
- `dev/docs/terminology/_search_record.py:91-120`
- `dev/docs/terminology/_unified_record.py:268-280`
- `dev/docs/terminology/_unified_record.py:336-345`
- `dev/docs/terminology/_unified_record.py:386-415`
- `src/cadrumo/domain/calculations/registry/_queries.py:766-817`
- `dev/docs/pagefind_inject.py:130-145`
- `dev/docs/pagefind_inject.py:360-399`
- `dev/docs/terminology/_coverage.py:173-186`
- `dev/docs/terminology/_coverage.py:251-321`
- `src/cadrumo/_data/terminology/evaluation/coverage-report.json:4-13`
- `docs/_static/cadrumo-docs.js:356-420`
- `dev/docs/terminology/_resolution.py:321-375`
- `src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/casillas/0001-casillas.toml:221-234`
- `.vault/adr/2026-08-01-user-docs-search-consolidation-adr.md`
