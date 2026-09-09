---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:1679c071ddd91f14c1ef0d15626274fde64281340276a73539a9449f9f756442'
step_id: 'S327'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the filename-keyed IVA observation source census and stale omission exemption

## Scope

- `rate-observation source census`
- `direct candidate and binding behavior`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_iva_observation_carries_its_rate.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/aggregation/tests/test_iva_ledger_candidates.py src/cadrumo/application/aggregation/tests/test_iva_deduction_fact_taxonomy.py src/cadrumo/domain/calculations/registry/tests/test_ledger_iva_aggregation_binding.py src/cadrumo/domain/calculations/registry/tests/test_rate_specific_box_pins_its_rate.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

Exact remeasurement reports the campaign's remaining live signal: 36 unreachable modules and 279 unused symbols.
