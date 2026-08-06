---
tags:
  - '#exec'
  - '#semantic-search-precompile-boundary'
date: '2026-08-01'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:2564cf2b97d29d5efad28e07b26a369bbe61594fa603c04ddc40ef50a466cb1d'
step_id: 'S04'
related:
  - "[[2026-07-31-semantic-search-precompile-boundary-plan]]"
---

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
