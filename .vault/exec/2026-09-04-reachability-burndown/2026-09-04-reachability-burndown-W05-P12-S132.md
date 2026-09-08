---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:fe2fe51f81068c6825e631532dbf6a25be221ddc9d5f68906d3c1cf8cc75fc01'
step_id: 'S132'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Remove the hard-coded M100 filing-year branch from inventory resolution and derive the applicable ledger year from the selected revision's typed inventory binding selectors

## Scope

- `inventory source resolver`
- `live regulatory-literal gate`
- `and inventory resolver tests`

## Changes

- `M` `src/cadrumo/application/aggregation/_inventory.py`
- `M` `src/cadrumo/application/aggregation/tests/test_inventory_source.py`
- `verify:` `uv run ruff check inventory resolver and regulatory-literal detector paths` -> `pass`
- `verify:` `uv run pytest -q -n0 selector-coordinate refusal and regulatory-literal detector tests` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.modelo_regulatory_literals` -> `pass`
