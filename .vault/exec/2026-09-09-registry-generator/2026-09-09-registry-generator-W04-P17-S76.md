---
tags:
  - '#exec'
  - '#registry-generator'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:c7c56a70751cc7d4762cb1aee91fd4a16d53abfa41517d6766208571f93f9702'
step_id: 'S76'
related:
  - "[[2026-09-09-registry-generator-plan]]"
---

# Declare the 161 manifested artefacts that are expressible under the static-files base but named by no required entry, matching each declaration URL to the manifest URL or alias so the pull stays additive

## Scope

- `dev/corpus/sync_aeat_record_design_corpus.py`

## Changes

- `M` `dev/corpus/sync_aeat_record_design_corpus.py`
- `verify:` `uv run --no-sync python dev/corpus/sync_aeat_record_design_corpus.py` -> `pass`

## Notes

159 of the 161 undeclared static-host artefacts were declared. Two were withheld and are
not debt of this Step: `modelo_123/files/01-...xls.txt` and `.../02-...xls.txt` are sheet-text
extractions carrying the URL of the `.xls` beside them, so no declaration could make them
reproducible from it. They are named in `_EXTRACTION_SIDECAR_ARTEFACTS` and refused as a
third class.

Two declared rows carry `page_key = None`: M145 `dr145v20.pdf` and M280 `DR_280_2022.pdf`
record their own file URL as `source_page`, and each is the only artefact of its modelo, so
no index page can be derived. `page_key` gained an optional state rather than a guessed value.
