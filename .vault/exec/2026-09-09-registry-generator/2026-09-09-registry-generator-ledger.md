---
tags:
  - '#exec'
  - '#registry-generator'
date: '2026-09-09'
modified: '2026-10-01'
body_schema: 'body-v2'
body_hash: 'sha256:7ce799bbc314ed4bb18c5084b7a232ba9a395b54ac91447805b09fe5371f7a36'
related:
  - "[[2026-09-09-registry-generator-plan]]"
---

# `registry-generator` ledger

## Changes

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
- `S51` `A` `.vault/reference/2026-09-09-registry-generator-consumer-behaviour-reference.md`
- `S53` `A` `.vault/reference/2026-09-09-registry-generator-consumer-behaviour-reference.md`
- `S54` `A` `.vault/reference/2026-09-09-registry-generator-consumer-behaviour-reference.md`
- `S55` `A` `.vault/reference/2026-09-09-registry-generator-consumer-behaviour-reference.md`

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
- `S51` 2026-10-01 reconciliation: recovered a missing ledger receipt; this is not a new source change or a rerun of historical tests. Evidence: .vault/reference/2026-09-09-registry-generator-consumer-behaviour-reference.md. The retained artifact supports the historical investigation or review outcome; no current test run is claimed. A denotes recovery of this retained artifact into the Step ledger, not creation of a new artifact today.
- `S53` 2026-10-01 reconciliation: recovered a missing ledger receipt; this is not a new source change or a rerun of historical tests. Evidence: .vault/reference/2026-09-09-registry-generator-consumer-behaviour-reference.md. The retained artifact supports the historical investigation or review outcome; no current test run is claimed. A denotes recovery of this retained artifact into the Step ledger, not creation of a new artifact today.
- `S54` 2026-10-01 reconciliation: recovered a missing ledger receipt; this is not a new source change or a rerun of historical tests. Evidence: .vault/reference/2026-09-09-registry-generator-consumer-behaviour-reference.md. The retained artifact supports the historical investigation or review outcome; no current test run is claimed. A denotes recovery of this retained artifact into the Step ledger, not creation of a new artifact today.
- `S55` 2026-10-01 reconciliation: recovered a missing ledger receipt; this is not a new source change or a rerun of historical tests. Evidence: .vault/reference/2026-09-09-registry-generator-consumer-behaviour-reference.md. The retained artifact supports the historical investigation or review outcome; no current test run is claimed. A denotes recovery of this retained artifact into the Step ledger, not creation of a new artifact today.
