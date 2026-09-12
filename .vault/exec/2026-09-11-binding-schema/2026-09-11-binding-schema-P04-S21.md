---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:8e3f178f6d423154cd13db337916cee033ee1fb3f162bfc147e6541fc7a7b7f7'
step_id: 'S21'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Re-derive the value contract of the 40 modelo 100 bindings whose consuming casillas omit data_type from provider-side evidence (profile field types, formula operands, resolver output channel), author the casilla data_type where it is missing, and refuse any row with no evidence

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/*/bindings/*.toml`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/*/casillas/*.toml`

## Changes

- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/bindings/0066-renta-2025-maritime-exempt-income-0525.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/bindings/0042-renta-2024-rental-reduccion-art-23-2-tier.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/bindings/0049-renta-2025-profile-madrid-nacimiento-adopcion-eligible-count.toml`
- `A` `src/cadrumo/domain/renta/rental_reduction.py`
- `M` `src/cadrumo/core/aggregation.py`
- `M` `src/cadrumo/domain/calculations/registry/binding_value_contract.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_value_contract.py`
- `M` `dev/registry/convert_binding_provider_shape.py`
- `M` `dev/registry/tests/test_convert_binding_provider_shape.py`
- `M` `dev/registry/tests/test_m100_rental_reduccion_art23_2.py`
- `M` `dev/registry/tests/test_modelo_100_registry_roles_madrid.py`
- `verify:` `load_modelo_directory(src/cadrumo/_data/registry/aeat/modelos/100)` -> `pass`
- `verify:` `uv run --no-sync python -m dev.registry.pipeline publish-authority` -> `fail`

## Notes

- 38 of the 40 in-scope binding ids were left unchanged: they carry a value contract that provider-side evidence confirms.
- No casilla `data_type` was authored. `CasillaDefinition.data_type` already defaults to `CasillaDataType.MONEY`, so authoring `money` onto the consuming casillas that omit it would restate the schema default without changing compiled behaviour.
- `publish-authority` exits 1 on 166 modelo 353 export fields referencing unknown bindings, in another writer's uncommitted area. The captured output contains no modelo 100 diagnostic.
