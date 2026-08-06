---
tags:
  - '#exec'
  - '#semantic-search-precompile-boundary'
date: '2026-08-01'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:161ba1078e51e8193a6150b169e87cb280e771da783facc9e1a97e52bd372ba8'
step_id: 'S07'
related:
  - "[[2026-07-31-semantic-search-precompile-boundary-plan]]"
---

# Regenerate the apidocs stubs for the deleted modules, verify clean collect-only, and land the whole phase as one atomic explicit-pathspec commit

## Scope

- `docs/api/`

## Description

- Regenerate the apidocs stubs for the three deleted `corpus_search` modules via the `dev.docs.apidocs` scaffold CLI, removing the orphaned `.rst` stubs and the parent toctree entries.
- Verify clean `pytest --collect-only` before landing.
- Land Phase P02 (steps S03-S07) as one atomic explicit-pathspec commit, per the plan's Parallelization constraint that the phase is one work unit and must not be dispatched to parallel agents.

## Outcome

Landed as commit `2933492a88` "refactor(search): retire the runtime embedding stack from the product". Confirmed by `git show --stat 2933492a88`: `docs/api/cadrumo.application.corpus_search._embed_build.rst`, `..._model_loader.rst`, and `..._query_embed.rst` show as full deletions (7 lines each), and `docs/api/cadrumo.application.corpus_search.rst` (the parent toctree) shrank by 3 lines to drop the orphaned entries. `pytest --collect-only -q src/cadrumo` reported clean at 15109/18487 at landed HEAD; `python -m dev.docs.apidocs scaffold --check` exited 0; `ruff check` was clean.

A follow-up commit `93074796e7` "docs(search): correct four docstrings still claiming semantic retrieval" landed after this phase, correcting stale prose in `_lexical_index.py` (three sites) and `_models.py` in `corpus_search` that this phase's rewire left behind (module docstrings and comments still describing a hybrid/semantic surface, a degraded no-download mode, and an embedding-matrix row-alignment rationale that no longer apply). Prose-only, no behaviour change; it is the closest existing analogue to the P04.S11/S12 surface-truth sweep but is scoped to two modules only, not the full docstring/harness/user-docs sweep those steps still owe.

## Notes

None for this step's own scope. The follow-up docstring correction above is noted for continuity but does not substitute for P04.S11/S12, which remain open.
