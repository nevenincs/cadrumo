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
