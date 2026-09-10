---
tags:
  - '#exec'
  - '#sociedades-manual-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:585bc284e619cb09a4c89f66a9cd25823ac0b9d9b25c7432a209f27494d693c8'
step_id: 'S08'
related:
  - "[[2026-09-10-sociedades-manual-coverage-plan]]"
---

# Replace Sociedades standing acquisition exceptions with catalogue-driven temporal coverage tests

## Scope

- `dev/corpus/tests/test_extraction_sidecar_freshness.py`

## Changes

- `M` `dev/corpus/tests/test_extraction_sidecar_freshness.py`
- `verify:` `uv run pytest dev/corpus/tests/test_extraction_sidecar_freshness.py -k "supported_tax_manual_matrix or manual_pdf_corpus_text_sidecars_exist or every_corpus_pdf_has_a_corpus_text_sidecar"` -> `pass`
