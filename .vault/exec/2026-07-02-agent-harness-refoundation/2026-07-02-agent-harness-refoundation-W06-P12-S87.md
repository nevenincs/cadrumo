---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:15c62c211d8e0225c6ac1484791817b483c7280cbcd02ab0f489f46b25b1f399'
step_id: 'S87'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Confirm the potion-multilingual-128M packaged footprint and that the wheel ships the precomputed vectors but no model weights, onnxruntime, or caches

## Scope

- `src/aeat/application/corpus_search/tests/test_search_shippability.py`

## Description

- Assert the degraded lexical-only mode imports without the search extra: the lexical-index and citation-lookup modules and the package facade import through real import machinery, and the embedding path refuses with the install hint (or does not refuse when the extra is present) — a real environment branch, never a skip.
- Walk the `corpus_search` package tree and assert it ships no model weights, onnxruntime, caches, precompiled index, or numpy matrix (a forbidden-suffix and forbidden-directory sweep), and walk the whole bundled `_data` tree asserting it ships no model weights.
- Assert the shipped light data is present: the bundled corpus carries over one hundred `*.extracted.json` triples the index builds from.
- Assert the FTS index build is deterministic: two builds over the same sample corpus produce identical ordered chunk-id sequences matching the chunker output.
- Cover the index-plus-lookup path with the sibling `test_lexical_index.py` and `test_citation_lookup.py` tests built from real bundled corpus files.

## Outcome

The licence/footprint gate is green: the wheel ships the precomputed-vector-ready light corpus data and no model artifacts, the degraded mode is importable with no semantic dependency, and the index build is deterministic. The full `corpus_search` suite passes (28 tests) and the packaged-data assertions confirm what SHIPS rather than depending on any optional model download.

## Notes

The download-size confirmation for `potion-multilingual-128M` is structured as an assertion on the packaged-data tree (no weights ship) rather than on the optional runtime download, per the Step contract that forbids skipping. Process incident: this Step's test file was swept into the peer coordinator baseline commit `c955c0496d` before this executor's per-Step pathspec commit; the code is committed and the gate is green at HEAD. S89 (the `search` extra pin in `pyproject.toml`/`uv.lock`) is deferred: both files carry live peer WIP (a `vaultspec-rag` core-dependency addition and a full re-lock), so re-locking would entangle that campaign's change; the coordinator was notified.
