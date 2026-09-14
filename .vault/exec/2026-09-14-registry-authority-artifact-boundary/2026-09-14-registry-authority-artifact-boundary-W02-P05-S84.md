---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:a776bb2c5c5e23716cdf53683716499967457100d76a09b305f82207e2a074e4'
step_id: 'S84'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---
# Migrate the inventoried live, overview/calendar_warnings.py, foreign_asset_thresholds.py, spreadsheet CLI, domain/portals/registry.py and domain/transactions/m210_income_classification.py consumers

## Scope

- `model discovery consumer migration`

## Changes

- `M` `src/cadrumo/application/overview/calendar_warnings.py`
- `M` `src/cadrumo/application/foreign_asset_thresholds.py`
- `M` `src/cadrumo/entrypoints/cli/modelo_spreadsheet_cli.py`
- `M` `src/cadrumo/domain/portals/registry.py`
- `M` `src/cadrumo/domain/transactions/m210_income_classification.py`
- `verify:` `checkpoint B focused import census` -> `pass`
