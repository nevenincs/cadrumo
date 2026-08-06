---
tags:
  - '#exec'
  - '#semantic-search-precompile-boundary'
date: '2026-08-01'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:d241fbf532629a17f9e16fad9e3d13d28521bad9c10a7bf210edcb95062761c8'
step_id: 'S03'
related:
  - "[[2026-07-31-semantic-search-precompile-boundary-plan]]"
---

# Rewire search_corpus and hybrid retrieval to lexical plus citation only, deleting the embedder wiring, vector loading, and semantic fusion, and reconcile every RetrievalMode consumer to the narrowed member set

## Scope

- `src/cadrumo/application/corpus_search/_runtime.py`

## Description

- Rewire `_runtime.py` (`search_corpus`, hybrid retrieval) to lexical plus citation only; delete the embedder wiring, vector loading, and semantic fusion branches.
- Rename `hybrid_search` to `run_retrieval` since no semantic half remains to be hybrid with.
- Narrow `RetrievalMode` (drop `HYBRID`) and `RetrievalHit` (drop `semantic_rank`), reconciling every consumer to the narrowed member set.
- Have corpus hits carry the BM25 relevance directly instead of a fused semantic/lexical score.

## Outcome

Landed as part of the single atomic commit `2933492a88` "refactor(search): retire the runtime embedding stack from the product", together with steps S04-S07 (the phase's one-work-unit constraint). `_runtime.py` shrank by ~55 lines removing embedder/vector/fusion logic; `_retrieval.py` and `_models.py` were reconciled in the same commit for the narrowed `RetrievalMode`/`RetrievalHit` shape.

## Notes

None. This step's diff cannot be isolated from S04-S07 in the git history because the plan's Parallelization section mandated the phase land as one atomic explicit-pathspec commit; the file-level evidence above is drawn from `git show --stat 2933492a88`.
