---
tags:
  - '#audit'
  - '#docs-terminology-search'
date: '2026-06-14'
modified: '2026-06-14'
related:
  - '[[2026-06-10-docs-terminology-search-adr]]'
  - '[[2026-06-10-docs-terminology-search-plan]]'
  - '[[2026-06-12-docs-terminology-search-close-honesty-audit]]'
  - '[[2026-06-12-docs-terminology-search-live-verification-audit]]'
  - '[[2026-06-12-docs-terminology-search-rung2-adjudication-audit]]'
---

# `docs-terminology-search` audit: `RAG corpus completion and Ctrl-K backend wiring`

## Scope

Completion pass over the docs terminology search feature after the resident
vaultspec-rag dependency was upgraded (now `v0.2.21`). The structurally-closed
plan carried one operational residual (CLOSE-003: the committed relevance
artifact was a degraded sweep with 76 failed queries and an 80% held-out
miss-rate, recorded when the prior RAG service saturated under a peer index
rebuild) and two unfinished backend seams discovered during this pass. This
audit covers the dependency re-inspection, the full corpus recompilation, the
seam fixes, the rung-2 re-adjudication, and the gates run.

## Findings

### DONE-001 | VERIFIED | The upgraded RAG interface is compatible and fast

The sweep retrieval client (`ServiceRagSearchClient`) parses the `v0.2.21`
service JSON envelope unchanged (`data.results[].path/line_start/line_end/score`).
A direct `regla de prorrata` code search returns the LIVA Article 102 legal row
and the extracted normatives corpus at score `0.99` in ~1.7 seconds. The
original degradation was service saturation, not an interface break: a full
94-query sweep now completes in ~3 minutes against the freshly reindexed store.

### DONE-002 | VERIFIED | The committed relevance corpus is complete and non-degraded

After an incremental `index --type all` reindex (codebase + vault) and a full
sweep over the 40 enrolled, term-bearing concepts, the committed mapping records
94 queries, 0 failed queries, and 94 of 94 queries with targets. The prorrata
worked example resolves across surfaces: its concept card, an M390 casilla
record, the IVA prorrata code module, and the LIVA Article 104/102 BOE legal
grounding. The relevance-data drift and laundering gates pass over the refreshed
artifact (every target resolves in the current build; only ids/targets/weights
ship).

### DONE-003 | FIXED | The originating concept card is now a guaranteed sweep target

A swept query string is, by construction, a declared label of its concept, yet
the sweep relied on RAG to re-discover the concept's own authoring fragment.
For generic or ambiguous surface forms (the English "box", the bare
"modelo 303") that fragment scored below the strong-signal floor or was
outranked, so the term mapped to no concept card. The sweep now seeds each
query's originating concept card deterministically at the concept tier weight,
ahead of the RAG-discovered grounding surfaces (the card is enrolment fact, not
a retrieval guess). This makes every shipped query resolve and is consistent
with the ADR's first-class-concept decision.

### DONE-004 | FIXED | The relevance boost now parses the sweep's actual output format

The Pagefind injection's relevance loader expected a flat `{"weights": {id: w}}`
map, but the sweep writes (and the relevance-data gate validates) a nested
`SweepResult` (`mappings[].targets[]`). The mismatch meant the loader picked up
top-level provenance keys (`query_count`, `score_floor`) as bogus weights and
ignored every real `record_id`; the committed corpus had never actually boosted
the index. The loader now parses the `SweepResult` and derives a
`record_id -> strongest ranking_weight` boost map (212 boosted records from the
current corpus).

### DONE-005 | FIXED | The Ctrl-K corpus now compiles in the docs build driver

The Pagefind post-build pass (`build_search_index` + the record injector) was
implemented and unit/integration tested but never invoked by the docs build
driver, so a real `just docs` produced no search index. The driver now compiles
the corpus after a successful full Sphinx build. A full compile over the built
HTML produces 1776 indexed pages plus 6077 injected term/casilla/CLI records
(59 relevance-boosted) into the per-language Pagefind index. Changed-page and
single-page preview builds deliberately skip the index.

### DONE-006 | RE-ADJUDICATED | Rung-2 static embeddings stay deferred by honest measurement

With the non-degraded corpus the held-out adjudicator no longer demands a
refresh: 5 of 5 held-out cases hit, 0% miss-rate, 0 failed queries, decision
`keep-deferred`. The residual closed-vocabulary queries are served first-class
by the seeded concept card and the four-language declared aliases (rung 1);
rung-2's unique capability is live embedding of UNCATALOGUED free text, which no
held-out miss exercises. Shipping a ~1-3 MB static term-embedding matrix is not
justified by this measurement.

### DONE-007 | VERIFIED | Gates are green for the touched surface

`ruff check`, `ruff format`, and `ty check` pass on every touched module. The
focused slice `pytest src/aeat/terminology dev/docs/terminology` is 190 passed,
the Pagefind index/inject integration tests and the prorrata end-to-end
Playwright smoke gate are 16 passed, and the consolidated unit/docs lane across
the terminology and Pagefind surfaces is 201 passed. The degraded-snapshot
assertions in the miss-rate gate were updated to the non-degraded invariants;
the below-floor sweep test was updated to assert the new concept-card-seed
guarantee.

## Recommendations

- Re-run the sweep on cadence (registry, legal-catalogue, or docs-structure
  changes) and review the `relevance.json` diff like any generated-but-committed
  surface; the drift gate fails loudly when a target goes stale.
- Keep rung-2 deferred until a held-out set that contains genuine uncatalogued
  free-text queries measures a material miss-rate against a non-degraded sweep.
- Leave the full-materialisation wiring proof in the integration lane only; the
  driver test uses a concept-subset injector seam so it runs in seconds.

## Codification candidates

No new codification candidates. The constraints exercised here are already
covered by existing project rules (`shipped-search-licence-clean`,
`terminology-single-declaration`, `terminology-scaffold-preserve-contract`) and
the ADR's measured rung-2 gate. The seam fixes are feature-specific, not
cross-session constraints.
