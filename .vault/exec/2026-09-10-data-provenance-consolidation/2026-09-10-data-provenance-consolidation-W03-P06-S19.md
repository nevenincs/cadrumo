---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:c31072a3c6b1d7fff2988bbe546385f4a1e807cbbbb137a6073fff911500ca6a'
step_id: 'S19'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# Replace sync-only extracted-sidecar census with explicit catalog derivation records

## Scope

- `dev/corpus/sync_aeat_record_design_corpus.py`

## Changes

- `M` `dev/corpus/sync_aeat_record_design_corpus.py`
- `M` `dev/corpus/tests/test_record_design_support.py`
- `verify:` `uv run pytest dev/corpus/tests/test_record_design_support.py -q` -> `pass`
