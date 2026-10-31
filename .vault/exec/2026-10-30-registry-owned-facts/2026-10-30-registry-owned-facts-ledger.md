---
tags:
  - '#exec'
  - '#registry-owned-facts'
date: '2026-10-30'
modified: '2026-10-31'
body_schema: 'body-v2'
body_hash: 'sha256:a47b5ef69330668086b8fdf24072ae191bc60b729c28036372813d2dede04249'
related:
  - "[[2026-10-30-registry-owned-facts-plan]]"
---

# `registry-owned-facts` ledger

## Changes

- `S01` `M` `src/cadrumo/application/modelo/dt12_advisory.py`
- `S01` `M` `src/cadrumo/application/filing/m190_context_validation.py`
- `S01` `M` `src/cadrumo/application/filing/m280_context_validation.py`
- `S01` `verify:` `pytest focused dt12 m190 m280` -> `pass`
- `S02` `M` `src/cadrumo/application/modelo/projection.py`
- `S02` `M` `src/cadrumo/application/calculations/m303_regimen_simplificado_annual_summary.py`
- `S02` `M` `src/cadrumo/domain/calculations/registry/m303_orden_constants.py`
- `S02` `M` `src/cadrumo/domain/calculations/registry/ledger_binding_validation.py`
- `S02` `verify:` `pytest focused registry and consumer suites` -> `pass`
- `S02` `verify:` `lint-imports` -> `fail`
- `S03` `M` `src/cadrumo/domain/contribuyente/renta_codes.py`
- `S03` `M` `src/cadrumo/domain/calculations/registry/descendant_disability_catalogue.py`
- `S03` `M` `src/cadrumo/application/wizard/catalogue.py`
- `S03` `M` `src/cadrumo/application/wizard/command_parameters.py`
- `S03` `verify:` `lint-imports` -> `pass`
- `S05` `A` `src/cadrumo/_data/registry/aeat/facts/0163-modelo-202-instalment-payment-months.toml`
- `S05` `M` `src/cadrumo/domain/period.py`
- `S05` `M` `src/cadrumo/domain/renta/maritime_exemption.py`
- `S05` `M` `src/cadrumo/domain/renta/tests/test_maritime_exemption.py`
- `S05` `verify:` `test_maritime_exemption` -> `pass`

## Notes

- `S01` Modelo 190 incapacity clave rule, Modelo 280 extinction key and Modelo 720 per-class subclaves move to S03, which adds their registry source
- `S02` lint-imports stops on a syntax error at `dev/tests/test_import_quality_gate.py:727,` outside this Step
