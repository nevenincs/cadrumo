---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:827cfa6e5a95c21599cfe5faf11678b11d79286dfe7f9559244736b650cd174e'
step_id: 'S10'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# Route manifest loading, payload classification, and acquisition diagnostics through the catalog

## Scope

- `dev/corpus/sync_aeat_record_design_corpus.py`

## Changes

- `M` `dev/corpus/sync_aeat_record_design_corpus.py`
- `verify:` `uv run pytest dev/corpus/tests/test_record_design_support.py -q` -> `pass`
