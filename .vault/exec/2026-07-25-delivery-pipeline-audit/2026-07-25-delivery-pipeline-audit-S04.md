---
tags:
  - '#exec'
  - '#delivery-pipeline-audit'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S04'
related:
  - "[[2026-07-25-delivery-pipeline-audit-plan]]"
---

# D2 follow-up, relocate extract_manual_corpus_text under the same home as a second atomic commit tagged relocation:extract_manual_corpus_text sweeping the two justfile recipes, the sidecar-freshness tests, the self-referencing instructive strings, and the path comments in _validate_evidence and pyproject

## Scope

- `dev/packaging/extract_manual_corpus_text.py`
- `dev/corpus/`
- `justfile`
- `pyproject.toml`

## Description

Verify the corpus-text extractor relocation, which landed at HEAD ahead of this execution pass.

- Confirm the module is tracked at `dev/corpus/extract_manual_corpus_text.py`.
- Enumerate the full consumer set by `rg` before trusting any claim of completeness, since this module carries the wider set and an incomplete sweep is what breaks an atomic relocation.
- Confirm the two justfile recipes, the two sidecar-freshness gates, the three path comments in `_validate_evidence.py`, the packaging comment in `pyproject.toml`, and the module's own self-naming instructive strings all read the new home.
- Run both sidecar-freshness gates and the record-design consumer gate.

## Outcome

Structurally complete at HEAD, landed as one atomic explicit-path commit `ce58f0555b`, subject `relocation:extract_manual_corpus_text move corpus-text extractor to dev/corpus`, six files in one index.

The consumer sweep enumerated from the commit and re-confirmed by `rg` against the working tree:

- the module itself, moved as a git-detected rename, with four self-naming strings updated: two runnable-module invocations in its docstring, one path comment locating it relative to the repo root, and one operator-facing instructive string telling the reader which module to re-run.
- two justfile recipes, the extract recipe and its `--check` drift gate.
- the packaging comment in `pyproject.toml` naming the generator of the compressed sidecars.
- three comments and docstring references in `src/cadrumo/domain/calculations/registry/_validate_evidence.py`.
- the sidecar-freshness gate under `src/cadrumo/_data/corpus/tests/`, covering its import, a docstring, and its stale-state operator hint.
- the sidecar-freshness gate under `src/cadrumo/domain/calculations/registry/tests/`, covering two docstring references and the deferred import.

A tree-wide `rg` for the old packaging path returns no match outside `.vault/`, where historical exec and audit records legitimately retain it. No re-export bridge survives.

## Notes

This relocation met the discipline that the companion step did not: one commit, one index, canonical site and full consumer sweep together.

Semantic discovery was degraded throughout this pass, so the consumer set above was established by `rg` and cross-read against the commit's own file list rather than by semantic search, whose misses carry no evidential weight while the index is truncated.
