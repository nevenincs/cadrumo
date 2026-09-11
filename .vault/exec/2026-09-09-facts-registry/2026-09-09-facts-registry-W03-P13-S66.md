---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:bf8fca2715e9c5d3f7e394b2787295dc380ab3c0469f167ddd12a277d7268add'
step_id: 'S66'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# Replace generic fact selectors with provider-owned validated applicability coordinates before consumer-boundary verification

## Scope

- `src/cadrumo/domain/transactions/retencion_facts.py`, `src/cadrumo/domain/transactions/tipo_actividad_partitions.py`, and `dev/registry/tests/test_transaction_fact_coordinates.py`

## Changes

- Transaction fact facades require an explicit filing-period `effective_date`; withholding settlement chooses an evidenced value date before booked date and refuses when neither exists.
- Activity-selector resolution resolves only enrolled entity-set facts at that coordinate, retains legal/source provenance, and refuses pre-source or wrong-family results.
- `load_tipo_actividad_selectors` now accepts an explicit validated authority for direct governed-authority verification; its default remains the canonical bundled authority with no cache, compatibility parser, or fallback provider.
- `A` `dev/registry/tests/test_transaction_fact_coordinates.py`
- `verify:` `uv run ruff check src/cadrumo/domain/transactions/tipo_actividad_partitions.py dev/registry/tests/test_transaction_fact_coordinates.py` -> `pass`
- `verify:` `uv run pytest -q -n 0 dev/registry/tests/test_transaction_fact_coordinates.py` -> `2 passed`
- `verify:` independent review of the S66/S69 checkpoint -> `no findings`
