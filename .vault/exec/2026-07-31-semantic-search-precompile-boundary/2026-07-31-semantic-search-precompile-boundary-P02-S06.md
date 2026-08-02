---
tags:
  - '#exec'
  - '#semantic-search-precompile-boundary'
date: '2026-08-01'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:3229c6b601293805387248990e40d59e988e75badf75d8187f6278d414617a14'
step_id: 'S06'
related:
  - "[[2026-07-31-semantic-search-precompile-boundary-plan]]"
---

# Delete test_embed_build.py, test_query_embed.py, test_hybrid_real_model_recall.py, and test_hybrid_real_model_recall_live.py, and rewrite the semantic branches of the surviving corpus-search and command-search tests against the lexical-only shape

## Scope

- `src/cadrumo/application/corpus_search/tests/`

## Description

- Delete `test_embed_build.py` (109 lines), `test_query_embed.py` (191 lines), `test_hybrid_real_model_recall.py` (120 lines), `test_hybrid_real_model_recall_live.py` (141 lines), and `test_ranking.py` (45 lines, the deleted `_ranking.py` module's test).
- Rewrite the semantic branches of `test_retrieval.py`, `test_command_index.py`, `test_command_ranking_golden.py`, and `test_search_shippability.py` against the lexical-only shape.
- Swap the shippability gate's extra-dependent embed-refusal test for an AST sweep that fails by name if any shipped search module imports model2vec, huggingface_hub, numpy, onnxruntime, or torch, including behind a deferred or `TYPE_CHECKING` import; that AST sweep replaces the command-ranking golden set's network-exposure guard, whose subject no longer exists.
- Drop the now-obsolete sensitive-persistence-policy assertion tied to the deleted embedding path (`tests/test_sensitive_persistence_policy.py`).

## Outcome

Landed as part of the single atomic commit `2933492a88` (see S03's exec record for the phase-wide one-commit constraint). Confirmed by `git show --stat 2933492a88`: the four named test files plus `test_ranking.py` show as full deletions; `test_retrieval.py`, `test_command_index.py`, `test_command_ranking_golden.py`, and `test_search_shippability.py` show substantial rewrites (the shippability file alone changed 88 lines). Suite state verified at landed HEAD: 49 passed across `corpus_search`/`command_search` tests; the MCP tree passed 306 (288 parallel plus 18 serial re-run with `-n0`, because xdist held the serial tests out of the parallel run and the parallel number alone was a false green); 337 combined.

## Notes

None. Diff not separable from S03-S05/S07 (one atomic commit by design); evidence drawn from `git show --stat 2933492a88` and the verification run reported by the executing agent.
