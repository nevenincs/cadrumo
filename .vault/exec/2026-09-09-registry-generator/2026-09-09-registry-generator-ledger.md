---
tags:
  - '#exec'
  - '#registry-generator'
date: '2026-09-09'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:0415eb66ac1bd45ccf0a186458213cede323dfa3209286dc9967a96cd0b044fa'
related:
  - "[[2026-09-09-registry-generator-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `registry-generator` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->
- `S75` `M` `dev/corpus/sync_aeat_record_design_corpus.py`
- `S75` `M` `dev/corpus/tests/test_record_design_support.py`
- `S75` `M` `src/cadrumo/_data/corpus/aeat_official/disenos_registro/manifest.json`
- `S75` `verify:` `uv run --no-sync python dev/corpus/sync_aeat_record_design_corpus.py` -> `pass`
- `S75` `verify:` `uv run --no-sync pytest dev/corpus/tests/test_record_design_support.py` -> `pass`
- `S76` `M` `dev/corpus/sync_aeat_record_design_corpus.py`
- `S76` `verify:` `uv run --no-sync python dev/corpus/sync_aeat_record_design_corpus.py` -> `pass`
- `S77` `A` `src/cadrumo/_data/corpus/aeat_official/disenos_registro/off_host_sources.json`
- `S77` `M` `dev/corpus/sync_aeat_record_design_corpus.py`
- `S77` `verify:` `uv run --no-sync python dev/corpus/sync_aeat_record_design_corpus.py` -> `pass`
- `S78` `M` `dev/corpus/sync_aeat_record_design_corpus.py`
- `S78` `verify:` `uv run --no-sync python dev/corpus/sync_aeat_record_design_corpus.py` -> `pass`
- `S79` `M` `dev/corpus/tests/test_record_design_support.py`
- `S79` `M` `dev/corpus/sync_aeat_record_design_corpus.py`
- `S79` `verify:` `uv run --no-sync pytest dev/corpus/tests/test_record_design_support.py` -> `pass`
- `S79` `verify:` `uv run --no-sync ruff check dev/corpus/sync_aeat_record_design_corpus.py dev/corpus/tests/test_record_design_support.py` -> `pass`
- `S79` `verify:` `uv run --no-sync ty check dev/corpus/sync_aeat_record_design_corpus.py dev/corpus/tests/test_record_design_support.py` -> `pass`

## Notes

- `S76` 159 of the 161 undeclared static-host artefacts were declared. Two were withheld and are
- `S76` not debt of this Step: `modelo_123/files/01-...xls.txt` and `.../02-...xls.txt` are sheet-text
- `S76` extractions carrying the URL of the `.xls` beside them, so no declaration could make them
- `S76` reproducible from it. They are named in `_EXTRACTION_SIDECAR_ARTEFACTS` and refused as a
- `S76` third class.
- `S76` Two declared rows carry `page_key = None`: M145 `dr145v20.pdf` and M280 `DR_280_2022.pdf`
- `S76` record their own file URL as `source_page`, and each is the only artefact of its modelo, so
- `S76` no index page can be derived. `page_key` gained an optional state rather than a guessed value.
- `S78` The authority join alone proved insufficient and the invariant was widened during the Step.
- `S78` An extraction sidecar carries the URL of the payload it was extracted from, so it resolves to
- `S78` a declared required row and passes. The invariant therefore also requires the stored
- `S78` extension to match the extension the declared URL serves, which is what separates an artefact
- `S78` from a derivative wearing its source's URL. The planted-defect test in S79 is what surfaced
- `S78` this; the first implementation would have passed a corpus containing a third sidecar.
- `S79` `_authority_failures` was refactored to take its off-host declaration, corpus root and sidecar
- `S79` census as arguments so the planted defects run on a temporary tree with no monkeypatching of
- `S79` the production module and no mutation of the committed corpus.
