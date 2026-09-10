---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:029b3359ef82756bcba46a189a22ebde67863f6ee14e842c6f2d00d89333f56e'
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
