---
tags:
  - '#exec'
  - '#semantic-search-precompile-boundary'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:b70add477e8b57e3c0e7c1ae94f72cff85e5e4e3dc5aeafe4ac2578b210431f3'
step_id: 'S06'
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
     The S06 and 2026-07-31-semantic-search-precompile-boundary-plan placeholders are machine-filled by
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
     The Delete test_embed_build.py, test_query_embed.py, test_hybrid_real_model_recall.py, and test_hybrid_real_model_recall_live.py, and rewrite the semantic branches of the surviving corpus-search and command-search tests against the lexical-only shape and ## Scope

- `src/cadrumo/application/corpus_search/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
