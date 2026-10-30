---
tags:
  - '#exec'
  - '#assets-core'
date: '2026-10-30'
modified: '2026-10-30'
body_schema: 'body-v2'
body_hash: 'sha256:7c807c00c44a9909a8836aff666a23416a86c0f5710572accf332982f6e7fdcf'
related:
  - "[[2026-10-30-assets-core-plan]]"
---

# `assets-core` ledger

## Changes

- `S01` `M` `src/cadrumo/domain/renta/actividad_asset/schedule.py`
- `S01` `M` `src/cadrumo/domain/renta/actividad_asset/tests/test_lifecycle.py`
- `S01` `verify:` `pytest src/cadrumo/domain/renta/actividad_asset/tests` -> `pass`
- `S01` `verify:` `pytest src/cadrumo/application/actividad_asset/tests` -> `pass`
- `S01` `verify:` `ruff check` -> `pass`
- `S05` `M` `src/cadrumo/domain/renta/actividad_asset/claims.py`
- `S05` `M` `src/cadrumo/domain/renta/actividad_asset/tests/test_claims.py`
- `S05` `M` `src/cadrumo/application/actividad_asset/history.py`
- `S05` `M` `src/cadrumo/application/actividad_asset/tests/test_history.py`
- `S05` `M` `src/cadrumo/application/aggregation/modelo_bindings_actividad_assets.py`
- `S05` `M` `src/cadrumo/application/actividad_asset/operation_dtos.py`
- `S05` `verify:` `pytest src/cadrumo/domain/renta/actividad_asset/tests` -> `pass`
- `S05` `verify:` `pytest src/cadrumo/application/actividad_asset/tests` -> `pass`
- `S05` `verify:` `pytest test_modelo_bindings_actividad_assets.py` -> `pass`
- `S05` `by:` `vaultspec-standard-executor`
- `S10` `A` `.vault/adr/2026-10-30-assets-core-disposal-adr.md`
- `S10` `M` `.vault/adr/2026-09-21-assets-core-lifecycle-contract-adr.md`

## Notes

- `S05` `operation_dtos.py` field removal lands with the S06 commit because the file shared another agent's edits.
