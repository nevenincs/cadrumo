---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S87'
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
     The S87 and 2026-07-02-agent-harness-refoundation-plan placeholders are machine-filled by
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
     The Confirm the potion-multilingual-128M packaged footprint and that the wheel ships the precomputed vectors but no model weights, onnxruntime, or caches and ## Scope

- `src/aeat/application/corpus_search/tests/test_search_shippability.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
