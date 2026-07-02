---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S77'
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
     The S77 and 2026-07-02-agent-harness-refoundation-plan placeholders are machine-filled by
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
     The Build the FTS5 lexical index with unicode61 remove_diacritics 2 plus a snowballstemmer Spanish stemmed column from the bundled extracted corpus triples and ## Scope

- `src/aeat/application/corpus_search/_lexical_index.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
