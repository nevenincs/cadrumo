---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:7ae0d012613304de6082259befab4a758618e123fa815b8fb47a8dd25caac45c'
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
- `verify:` `uv run pytest -n0 dev/registry/tests/test_generated_export_trees.py -q` -> `fail`

## Notes

The final export-reproduction gate is held open by an unresolved add/add merge conflict in `src/cadrumo/core/frozen_mapping.py`. The merged Modelo 222 state correctly retires its drift disposition and declares calculation authority, but pytest cannot import the registry harness while the conflict markers remain. No files in that concurrent merge were altered here.
