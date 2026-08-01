---
tags:
  - '#exec'
  - '#semantic-search-precompile-boundary'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:2305ad5e3238c650bd7c13cc2cc1cfbd5561cd8858aef9340a73ec98b90d3980'
step_id: 'S03'
related:
  - "[[2026-07-31-semantic-search-precompile-boundary-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace semantic-search-precompile-boundary with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-07-31-semantic-search-precompile-boundary-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Rewire search_corpus and hybrid retrieval to lexical plus citation only, deleting the embedder wiring, vector loading, and semantic fusion, and reconcile every RetrievalMode consumer to the narrowed member set and ## Scope

- `src/cadrumo/application/corpus_search/_runtime.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
