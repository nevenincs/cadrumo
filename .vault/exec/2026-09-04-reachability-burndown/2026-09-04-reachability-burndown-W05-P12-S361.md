---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:e0b43cd1e00f37c3380dccb7a7ab85552d4cba6395f0607ca2b15eb00ead7a82'
step_id: 'S361'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Remove ten unused Modelo 193 withholding-field aliases left by the extracted field-finalization module.

## Scope

- `withholding row assembly aliases`
- `Modelo 190/193 owner tests`
- `exact unused-symbol signal`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/_withholding_rows.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/domain/calculations/registry/tests/test_modelo_190_193_round_trip.py src/cadrumo/domain/calculations/registry/tests/test_modelo_193_records_fill_the_declared_length.py -q` -> `pass (5 passed)`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/_withholding_rows.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (240 unused symbols; down from 250)`
