---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:a91fb8420e577a69b78edd42d4f08e93f08f8855e03adf7a3c9259f27f414214'
step_id: 'S10'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Serialize the typed provider member in query projections and route alternate-binding re-splats through the canonical accessor

## Scope

- `src/cadrumo/domain/calculations/registry/query_reports.py`
- `src/cadrumo/domain/calculations/registry/queries.py`
- `src/cadrumo/application/aggregation/modelo_bindings.py`
- `src/cadrumo/application/aggregation/iva_ledger.py`
- `dev/docs/casilla_reference.py`
- `dev/registry/compiler/_validate_export_exemption.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/query_reports.py`
- `M` `src/cadrumo/domain/calculations/registry/queries.py`
- `M` `src/cadrumo/application/aggregation/modelo_bindings.py`
- `M` `src/cadrumo/application/aggregation/iva_ledger.py`
- `M` `dev/docs/casilla_reference.py`
- `M` `dev/registry/compiler/_validate_export_exemption.py`
- `verify:` `uv run ruff check <touched>` -> `pass`
- `verify:` `uv run ty check <touched>` -> `pass`
- `verify:` `uv run basedpyright <touched>` -> `pass`

## Notes

The flattened `BindingSelectorQueryProjection`, `BindingSelectorQueryEntry` and
`BindingSelectorQueryValue` models and their `_public_selector` /
`_public_selector_value` projectors were deleted; the binding query row now
carries the typed `provider` union member itself.

`src/cadrumo/domain/calculations/registry/tests/test_queries.py` still asserts
against the deleted projection and needs migration to the typed member.
