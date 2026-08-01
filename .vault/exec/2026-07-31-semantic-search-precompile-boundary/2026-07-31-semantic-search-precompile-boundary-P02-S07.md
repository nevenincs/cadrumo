---
tags:
  - '#exec'
  - '#semantic-search-precompile-boundary'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:c9f460c52e4fe0ec070dd428d7701c48f3bededbd98a49a34730cfd4da0ed5fa'
step_id: 'S07'
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
     The S07 and 2026-07-31-semantic-search-precompile-boundary-plan placeholders are machine-filled by
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
     The Regenerate the apidocs stubs for the deleted modules, verify clean collect-only, and land the whole phase as one atomic explicit-pathspec commit and ## Scope

- `docs/api/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
