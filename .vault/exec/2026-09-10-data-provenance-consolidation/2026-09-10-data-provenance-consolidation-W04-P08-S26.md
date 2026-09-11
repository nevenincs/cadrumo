---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:0d8ca37d6bd3ef3a42d6b15e1e67bf7b9c7886e14636ccecd85b0efb5c306f8a'
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

The final export-reproduction gate is held open by a concurrent Modelo 222 state transition: its records now reproduce, but `dev/registry/pipeline/generated_tree_dispositions.toml` still carries a `record_drift` row and the paired reproduction pin still treats the revision as below calculation grade. The full live run otherwise passed every generated-tree case. No files in that registry work were altered here.
