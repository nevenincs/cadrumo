---
tags:
  - '#exec'
  - '#semantic-search-precompile-boundary'
date: '2026-08-01'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:8a32b6407fe5b92b407c3378d15fbf5d9ea16455c23b5123687343536e0a975d'
step_id: 'S05'
related:
  - "[[2026-07-31-semantic-search-precompile-boundary-plan]]"
---

# Rewire the command-search index to per-column BM25 plus token-overlap only, deleting the model2vec semantic side, the RRF fusion, and the query_embedder parameter on the meta-tools builder

## Scope

- `src/cadrumo/application/command_search/_index.py`

## Description

- Rewire `command_search/_index.py` to per-column BM25 plus token-overlap ranking only.
- Delete the model2vec semantic side and the RRF fusion path.
- Drop the `query_embedder` parameter from the meta-tools builder.
- Have command hits carry a reciprocal-rank score instead of a fused semantic/lexical score, since the FTS5 and token-overlap paths have no comparable scale to surface raw.

## Outcome

Landed as part of the single atomic commit `2933492a88` (see S03's exec record for the phase-wide one-commit constraint). Confirmed by `git show --stat 2933492a88`: `command_search/_index.py` shrank by 143 lines (net) removing the semantic branches; `command_search/__init__.py` and `entrypoints/mcp/_corpus_tools.py` were reconciled in the same commit for the narrowed builder signature. `command_search/_index.py` was touched again in the P03.S08 commit `13935ef3a2` to delete the now-unreachable `ModuleNotFoundError` fallback branch for the stemmer, once snowballstemmer moved into core.

## Notes

None. Diff not separable from S03/S04/S06/S07 (one atomic commit by design); evidence drawn from `git show --stat 2933492a88`.
