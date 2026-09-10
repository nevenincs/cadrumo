---
tags:
  - '#exec'
  - '#registry-generator'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:43d836bbf55512a06ab8fef8da8ad4ec5090e3d81be4b278b336d8685b8977f5'
step_id: 'S79'
related:
  - "[[2026-09-09-registry-generator-plan]]"
---

# Prove the invariant has teeth by planting an undeclared artefact on a temporary corpus tree and asserting the check refuses it, with the normal path passing in the same suite

## Scope

- `dev/corpus/tests/`

## Changes

- `M` `dev/corpus/tests/test_record_design_support.py`
- `M` `dev/corpus/sync_aeat_record_design_corpus.py`
- `verify:` `uv run --no-sync pytest dev/corpus/tests/test_record_design_support.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/corpus/sync_aeat_record_design_corpus.py dev/corpus/tests/test_record_design_support.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/corpus/sync_aeat_record_design_corpus.py dev/corpus/tests/test_record_design_support.py` -> `pass`

## Notes

`_authority_failures` was refactored to take its off-host declaration, corpus root and sidecar
census as arguments so the planted defects run on a temporary tree with no monkeypatching of
the production module and no mutation of the committed corpus.
