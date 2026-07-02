---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S89'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace agent-harness-refoundation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S89 and 2026-07-02-agent-harness-refoundation-plan placeholders are machine-filled by
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
     The Pin the search-stack dependencies snowballstemmer, model2vec, and numpy in the capability-gated search extra with a lexical-only degraded default and ## Scope

- `pyproject.toml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Pin the search-stack dependencies snowballstemmer, model2vec, and numpy in the capability-gated search extra with a lexical-only degraded default

## Scope

- `pyproject.toml`

## Description

- Add a capability-gated `search` optional-dependency extra pinning `model2vec>=0.8,<1` (the potion-multilingual-128M static query embedder), `snowballstemmer>=2.2,<4` (the Spanish stemmed FTS column), and `numpy>=1.26,<3` (the precomputed-vector cosine search).
- Keep the lexical-only mode the degraded default: the FTS index and citation lookup carry no extra dependency, so a bare-core install stays functional and only the semantic half rides the extra.
- Register the extra in the `all` convenience aggregate and re-lock `uv.lock`, resolving model2vec to 0.8.2.

## Outcome

The semantic-search stack is pinned in a licence-clean, capability-gated extra with a lexical-only degraded default, closing the last W06.P12/P14 build-step for the grounding surface. `uv lock` resolved 243 packages and `uv lock --check` confirms the lock is consistent with the manifest; the `corpus_search` suite stays green (28 passed) with the extra absent from the environment, exercising the real refusal path.

## Notes

This Step was pulled forward into the W06.P12 execution and was initially deferred because `pyproject.toml` and `uv.lock` carried a live peer `vaultspec-rag` core-dependency change plus its full re-lock; once that peer WIP committed, the files were clean and the extra was added cleanly. `uv add --optional` rolled back on a Windows file lock (a peer process held `aeat.exe` during the venv sync), so the extra was hand-authored into the manifest and locked with `uv lock`, which updates only the lock and never touches the venv. The model was not installed or downloaded: the potion download is the optional runtime path the shippability gate deliberately does not depend on, and confirming the exact packaged byte size and the pinned commit SHA remains the research doc's open verification item for the W06.P13 download-UX boundary.
