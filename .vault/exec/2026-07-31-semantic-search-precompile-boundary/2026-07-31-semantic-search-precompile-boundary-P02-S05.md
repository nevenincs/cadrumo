---
tags:
  - '#exec'
  - '#semantic-search-precompile-boundary'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:7ac2109b62efe57ae5d522c2c2c51d42cc3c5ae36beda05a3db09aa604c8f256'
step_id: 'S05'
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
     The S05 and 2026-07-31-semantic-search-precompile-boundary-plan placeholders are machine-filled by
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
     The Rewire the command-search index to per-column BM25 plus token-overlap only, deleting the model2vec semantic side, the RRF fusion, and the query_embedder parameter on the meta-tools builder and ## Scope

- `src/cadrumo/application/command_search/_index.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
