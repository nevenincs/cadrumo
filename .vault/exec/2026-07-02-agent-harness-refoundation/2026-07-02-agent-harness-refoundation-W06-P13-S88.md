---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S88'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Add brute-force numpy cosine vector search with RRF k=60 fusion in plain Python and a lexical-only FTS5-plus-citation degraded mode

## Scope

- `src/aeat/application/corpus_search/_retrieval.py`

## Description

- Add `hybrid_search`, which fuses the FTS5 lexical ranking with a brute-force numpy cosine ranking over the build-time-precomputed corpus matrix using Reciprocal Rank Fusion (k=60, each side capped at ~top-50) in plain Python.
- Short-circuit an exact citation id straight to the structured lookup (mode `CITATION`), returning the resolved verbatim text without ranking.
- Degrade cleanly to lexical-only (mode `LEXICAL_ONLY`) when no precomputed vectors or query embedder are supplied, or when the embedder refuses for want of the search extra, so a bare-core install still grounds against the corpus.
- Embed the live query through the runtime embedder, cosine-rank the corpus rows, and assemble typed `RetrievalHit` records carrying corpus_ref, verbatim chunk text, the fused score, and the per-side lexical and semantic ranks; fetch metadata for semantic-only hits from the index with parameterised single-id queries.
- Add typed `RetrievalMode`, `RetrievalHit`, and `RetrievalResponse` models and export the retrieval surface on the package facade.

## Outcome

The hybrid retrieval surface is complete and covers all three modes: citation short-circuit, hybrid fusion, and lexical-only degrade. Ties break deterministically (fused score, then lexical rank, then chunk id) so fused order is stable. The retrieval tests (landed under S84) exercise every mode over a real bundled-corpus index and pass (7); ruff and pyright are clean, and `_retrieval` is reachable in the module-coverage gate.

## Notes

The semantic side is isolated from the optional potion model download in tests by supplying a fixed real query vector, so the RRF, cosine, and assembly logic run on real numpy arrays without a network fetch. The dynamic-`IN` metadata query was replaced with parameterised single-id lookups to avoid the S608 SQL-string lint (the id list is at most `limit` items, so per-id fetches are cheap). The retrieval-test file was landed immediately after this code to close the module-coverage gate; the corpus-resource-read portion of S84 lands with S82.
