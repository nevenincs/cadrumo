---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:2b5f496af1c064d8ee7d3b8ea23d503fcfdb236f719eab908367d4860a214e9c'
step_id: 'S14'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# Migrate documentation-preprocessor freshness tests to the shared generic validator

## Scope

- `dev/docs/preprocess/tests/test_corpus_sidecar_freshness.py`

## Changes

- `M` `dev/docs/preprocess/tests/test_corpus_sidecar_freshness.py`
- `verify:` `uv run pytest dev/docs/preprocess/tests/test_corpus_sidecar_freshness.py -q` -> `pass`
