---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S80'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Add the runtime query embedder with model2vec potion-multilingual-128M behind the capability-gated extra with a pinned revision, app-controlled cache dir, and install hint

## Scope

- `src/aeat/application/corpus_search/_query_embed.py`

## Description

- Add `QueryEmbedder`, which lazily loads the pinned potion-multilingual-128M static model on first embed and caches it for reuse, embedding one query string into a 1-D float32 vector in the corpus embedding space.
- Refuse a blank query with a typed input error before any model load, and refuse a missing search extra with the install hint via the shared loader.
- Root the model download in an app-controlled cache directory derived from the Settings `aeat_local_storage_root` (`<root>/search-models`), so a bundled Desktop Extension keeps model state inside the one app state root rather than the user's global Hugging Face cache.
- Add `search_extra_available`, which reports whether model2vec is importable without triggering a model load, so the retrieval layer can choose hybrid versus lexical-only degraded mode.
- Extract the shared model2vec loader and dimensionality helper into a new `_model_loader` module so the build-time precompute and the runtime embedder share one capability gate instead of duplicating it.
- Add real-behavior tests (environment-branch, never skip) for availability reporting, storage-root-derived cache dir, lazy construction, empty-query refusal, and the install-hint refusal.

## Outcome

The live-query half of the semantic stack is in place and shares one capability gate with the build-time precompute. Construction is lazy and never loads the model, empty queries are refused before any load, and the absent-extra path refuses with the `pip install aeat[search]` hint in the current bare-core environment. Focused tests pass (5); ruff and pyright are clean; the pre-existing embedding tests stay green after the loader extraction (7 passed).

## Notes

The cache directory is derived from an existing Settings field rather than a new one, so no `core/config.py` field or env var was added and no Settings conformance test is disturbed. The actual model embedding is a network-download path (the potion weights) that the unit gate deliberately does not exercise, consistent with the shippability contract that the download is optional; the test asserts the shipped-default refusal branch. The `cache_dir` is passed to `from_pretrained` only when the installed model2vec signature accepts it; finalising the exact download/cache behaviour and the pinned commit SHA remains the research doc's open item for the download-UX.
