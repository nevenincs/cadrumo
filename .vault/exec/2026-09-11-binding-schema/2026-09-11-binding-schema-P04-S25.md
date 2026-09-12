---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:c4203c2a207bff637951c89dff6de4cad0f04877cf45dd6921eb0c831eb797c2'
step_id: 'S25'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Give the profile resolver and formula evaluator a real boolean channel so a declared boolean contract is never collapsed onto Decimal in transport; the modelo 100/2020 decimal casilla sweep is handed to the registry authoring lane pending the AEAT dictionary corpus

## Scope

- `src/cadrumo/application/modelo/profile_binding.py`
- `src/cadrumo/application/aggregation/source_mesh.py`
- `src/cadrumo/application/aggregation/source_resolution_operations.py`
- `src/cadrumo/domain/calculations/registry/formula_evaluation/`

## Changes

- `M` `src/cadrumo/application/aggregation/source_mesh.py`
- `M` `src/cadrumo/application/aggregation/source_resolution_operations.py`
- `M` `src/cadrumo/application/aggregation/terminal_origin_audit.py`
- `M` `src/cadrumo/application/modelo/profile_binding.py`
- `M` `src/cadrumo/application/modelo/binding_resolution.py`
- `M` `src/cadrumo/application/modelo/calculation_resolution.py`
- `M` `src/cadrumo/application/modelo/calculation_actions.py`
- `M` `src/cadrumo/application/modelo/taxation_comparison.py`
- `M` `src/cadrumo/domain/calculations/registry/formula_runtime.py`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/bindings/0006-renta-2024-profile-taxpayer-birth-date.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/bindings/0013-renta-2025-profile-taxpayer-birth-date.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/bindings/0001-bindings.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2025-y-siguientes/bindings/0001-bindings.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/210/revisions/2025/bindings/0001-bindings.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/210/revisions/2026-y-siguientes/bindings/0001-bindings.toml`
- `M` `src/cadrumo/_data/registry/authority/authority.json`
- `A` `dev/registry/tests/test_modelo_100_boolean_channel_transport.py`
- `verify:` `uv run --no-sync python -m dev.registry.pipeline publish-authority` -> `pass`
- `verify:` `uv run --no-sync pytest dev/registry/tests/test_modelo_100_boolean_channel_transport.py dev/registry/tests/test_modelo_100_boolean_channel_profile_bindings.py dev/registry/tests/test_modelo_100_anualidades_separate_escala_multiyear.py dev/registry/tests/test_lookup_bracket_by_ccaa.py -n 0 -m ''` -> `pass`
- `verify:` `uv run --no-sync ruff check && ty check && basedpyright <touched files>` -> `pass`

## Notes

Part B of the originating Step row (the modelo 100/2020 non-monetary `decimal`
casilla sweep) was reassigned to the registry authoring lane before any file
under that revision was written; no 2020 casilla was modified here.

Routing bindings by their authored `value.channel` surfaced three declarations
that contradicted their own consuming formulas or their own facts, each
corrected at the declaration rather than absorbed by the resolver: the modelo
100 taxpayer birth date declared `text` while consumed by `age_at_year_end`, the
modelo 210 country of fiscal residence declared `money` while consumed as an
enum dispatch key, and the modelo 200 new-entity flag declared `money` while its
profile fact is a boolean used only as an `if_then_else` predicate.

`src/cadrumo/domain/calculations/registry/formula_runtime.py` was found with a
concurrent contributor's `_merge_relation_values_into_bindings` interleaved into
the middle of `_resolve_calculation_inputs`, leaving that function returning
`None`. The ordering was repaired with both contributions preserved.
