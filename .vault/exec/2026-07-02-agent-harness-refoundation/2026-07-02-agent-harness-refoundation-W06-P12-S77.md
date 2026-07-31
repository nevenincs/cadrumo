---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:150d13ab49934dbd820b0f936f6e33d9e404849894e472bc1fb966af8d9c23b6'
step_id: 'S77'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Build the FTS5 lexical index with unicode61 remove_diacritics 2 plus a snowballstemmer Spanish stemmed column from the bundled extracted corpus triples

## Scope

- `src/aeat/application/corpus_search/_lexical_index.py`

## Description

- Add the `aeat.application.corpus_search` package with a top-level facade, plain-exception error hierarchy carrying `context`/`suggestion`, and strict frozen pydantic v2 records for chunks, hits, documents, and build results.
- Walk the bundled `*.extracted.json` corpus triples through the `aeat.core.resources` boundary in sorted filename order and split each extracted unit into paragraph-bounded prose chunks of roughly 1200 to 1500 characters.
- Mint a deterministic, unique chunk id per chunk from the source stem plus zero-padded unit and chunk ordinals so a rebuilt index re-mints byte-identical ids.
- Build the FTS5 index into a caller-supplied SQLite path with a diacritic-folded column (`unicode61 remove_diacritics 2`) and a second Spanish-Snowball-stemmed column, plus non-FTS chunk and document metadata tables.
- Add a BM25-ranked search primitive that queries both columns (raw terms folded, stemmed terms stemmed) and refuses an empty query or a non-positive limit.
- Add real-behavior tests over a small copied real-corpus subset covering chunk-id stability and uniqueness, recargo/extemporanea recall, diacritic folding, stemmed inflection recovery, input refusals, and the bundled-corpus chunk count.

## Outcome

The lexical half of the R3 grounding surface is live and licence-clean: standard-library `sqlite3` FTS5 plus `snowballstemmer` only, so the module imports and searches in the degraded no-download mode with no semantic dependency. The full bundled corpus yields 4027 chunks across 240 documents; a small-subset index build and search are deterministic and correct. Focused suite `test_lexical_index.py` is green (8 passed); ruff and pyright are clean on the package.

## Notes

The package facade is introduced with only the S77 surface exported and grown in the S78 and S79 commits, so each commit leaves the tree importable and green. The shared index (556 peer-staged files from concurrent campaigns) was left untouched: the commit used an explicit pathspec naming only the seven authored files. Exact-citation resolution is intentionally out of this Step: it is a structured registry-catalogue lookup, not FTS, and lands in S78.
