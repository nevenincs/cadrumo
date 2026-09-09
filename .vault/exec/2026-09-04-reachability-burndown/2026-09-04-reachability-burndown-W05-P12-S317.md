---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:7a321ad4841c78d6a67e698f1ea995df30601e42ee3a4fba4475551d3a754591'
step_id: 'S317'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the three-module per-modelo token baseline and embedded matcher corpus

## Scope

- `generic-module carveout ratchet`
- `focused modelo owner behavior`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_generic_module_modelo_carveouts.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/modelo/tests/test_projection_decimal_overrides.py src/cadrumo/application/modelo/tests/test_calculation_modelo_adjustments.py src/cadrumo/application/modelo/tests/test_cross_period_clean_state_enforcement.py` -> `fail`

## Notes

Thirty-four focused modelo behavior tests pass. The remaining peer-owned failure is `test_file_modelo_390_passes_clean_state_with_imported_bound_justificantes`, where the current M303 carry ingress now requires an official declaration-type header from its fixture; deleting the static token census does not touch that runtime path.
