---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:aaf88a20e24f53645cd9739a99865820db0a47f4e64a787b041a54e4ae297c30'
step_id: 'S80'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# Classify the remaining IVA structured tables and authorize deletion only with a typed, evidence-bearing provider replacement

## Scope

- `src/cadrumo/_data/registry/aeat/iva and src/cadrumo/domain/iva and dev/registry/compiler and dev/registry/analysis`

## Changes

- `M` `dev/registry/analysis/facts_iva_retirement.toml`
- `A` `dev/registry/tests/test_iva_structured_table_classification.py`
- `verify:` `uv run --no-sync ruff check dev/registry/analysis/facts_iva_retirement.toml dev/registry/tests/test_iva_structured_table_classification.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q dev/registry/tests/test_iva_structured_table_classification.py` -> `pass`

## Notes

- `catalogues.toml`, `place_of_supply.toml`, `territories.toml`, and `territory_carve_outs.toml` are retained until the four added typed-fact migrations preserve their legal semantics and evidence. `country_names.toml` is retained technical interoperability vocabulary, not a legal-fact adapter.
- Broader IVA tests remain blocked by the pre-existing missing published authority artifact; no deletion or fallback was introduced.
