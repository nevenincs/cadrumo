---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S79'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Precompute the corpus embeddings at build time with model2vec potion-multilingual-128M and ship the numpy matrix as bundled data

## Scope

- `src/aeat/application/corpus_search/_embed_build.py`

## Description

- Add `embed_corpus`, which lazily imports `model2vec` behind the capability-gated `search` extra and refuses with a typed dependency error carrying the `pip install aeat[search]` hint when it is absent, keeping the module importable in the degraded no-download mode.
- Embed chunk text with `potion-multilingual-128M` (pinned model id and tracked revision recorded on the result for provenance), write a float32 numpy matrix and a parallel chunk-id list to caller-supplied paths, and import numpy function-locally so the lexical-only surface never depends on it at import time.
- Add the `more_like_this` cosine top-k primitive over a precomputed matrix given a chunk id — the query-model-free "more-like-this-document" mode — plus a `load_embeddings` roundtrip loader, both numpy-only.
- Refuse an unknown query chunk id, a non-positive top_k, and a matrix/id length mismatch with typed input errors.
- Add real-behavior tests that branch on the real presence of `model2vec` (never skip): assert the install-hint refusal when absent (the shipped default) or a valid float32 matrix when present, plus cosine ranking, roundtrip, and the input refusals.
- Export the embedding surface on the package top-level facade.

## Outcome

The semantic half's build-time precompute is in place and licence-clean by construction: the model is needed only to embed, corpus vectors ship as plain data, and the more-like-this primitive runs over shipped vectors with numpy alone. The capability gate refuses cleanly with an install hint in the current bare-core environment, and the pure-numpy primitives are exercised unconditionally. Focused tests are green; ruff and pyright are clean (the optional `model2vec` import is typed through a rationale-tagged ignore, mirroring the existing browser/google optional-extra boundaries).

## Notes

The pinned model revision is tracked as a module default rather than a hard commit SHA: confirming the exact packaged byte size and pinned revision is the research doc's single open verification item, resolved at the download-UX boundary in W06.P13/S80; the revision rides through to the build-result record for provenance. Process incident: as with S78, this Step's implementation and test files were swept into the peer coordinator baseline commit `c955c0496d` before this executor's per-Step pathspec commit could run; the facade export landed in `6aa3ebca3e`. Code is committed and green at HEAD.
