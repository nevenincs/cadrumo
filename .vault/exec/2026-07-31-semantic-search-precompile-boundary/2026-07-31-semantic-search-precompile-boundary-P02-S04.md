---
tags:
  - '#exec'
  - '#semantic-search-precompile-boundary'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:8f4687be948005081c9524036095ccbd6637283829a17dee3d9eaeb9675b8659'
step_id: 'S04'
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
     The S04 and 2026-07-31-semantic-search-precompile-boundary-plan placeholders are machine-filled by
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
     The Delete _model_loader.py, _query_embed.py, and _embed_build.py together with their facade exports and error-surface references and ## Scope

- `src/cadrumo/application/corpus_search/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Delete _model_loader.py, _query_embed.py, and _embed_build.py together with their facade exports and error-surface references

## Scope

- `src/cadrumo/application/corpus_search/`

## Description

- Delete `_model_loader.py` (191 lines, the model2vec loader), `_query_embed.py` (119 lines, the query embedder), and `_embed_build.py` (205 lines, the corpus-vector precompute), plus `_ranking.py` (59 lines, the shared cosine/RRF ranking primitives the ADR also scoped for deletion).
- Remove their re-exports from `corpus_search/__init__.py`'s facade.
- Drop the now-subjectless allowlist entries the deletion made unreachable: the `embed_corpus` raw-write row, the `_embed_build` lazy-import edge, and the model2vec type-check gap (`dev/quality/types.py`, `dev/vulture_whitelist.py`).

## Outcome

Landed as part of the single atomic commit `2933492a88` (see S03's exec record for the phase-wide one-commit constraint). Confirmed by `git show --stat 2933492a88`: `_model_loader.py`, `_query_embed.py`, `_embed_build.py`, and `_ranking.py` all show as full deletions; `corpus_search/__init__.py` shrank by 57 lines and `command_search/__init__.py` by 20 lines to drop the facade exports; `dev/quality/types.py` and `dev/vulture_whitelist.py` were trimmed in the same commit.

## Notes

None. Diff not separable from S03/S05-S07 (one atomic commit by design); evidence drawn from `git show --stat 2933492a88`.
