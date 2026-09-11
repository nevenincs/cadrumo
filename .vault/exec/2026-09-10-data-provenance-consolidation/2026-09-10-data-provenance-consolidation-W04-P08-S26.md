---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:b3cdc8eb400b5bbe7174cab519f422eb2a413ed27b343d1baeb51c3ebfc12b5a'
step_id: 'S26'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# Verify sidecar, export, normative-text, and calculation-oracle contracts remain distinct

## Scope

- `dev/docs/preprocess/tests/test_corpus_sidecar_freshness.py`

## Changes

- `M` `src/cadrumo/_data/corpus/normatives/html/ley-12-2002.html`
- `M` `src/cadrumo/_data/corpus/normatives/html/ley-12-2002.html.extracted.json`
- `M` `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-48.html`
- `M` `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-48.html.extracted.json`
- `M` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-1.html`
- `M` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-1.html.extracted.json`
- `M` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-4.html`
- `M` `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008-art-4.html.extracted.json`
- `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-art-1.html`
- `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-art-1.html.extracted.json`
- `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-df-unica.html`
- `M` `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-df-unica.html.extracted.json`
- `M` `src/cadrumo/_data/corpus/normatives/html/rd-439-2007-art-95.html.extracted.json`
- `verify:` `uv run pytest -n0 dev/docs/preprocess/tests/test_corpus_sidecar_freshness.py -q` -> `pass`
- `verify:` `uv run pytest -n0 dev/corpus/tests/test_extraction_sidecar_freshness.py -q` -> `pass`
- `verify:` `uv run pytest -n0 dev/corpus/tests/test_extract_boe_article.py dev/registry/tests/test_oracle_parity.py -q` -> `pass`
- `verify:` `uv run pytest -n0 dev/registry/tests/test_generated_export_trees.py -q` -> `pass`
