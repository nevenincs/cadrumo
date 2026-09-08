---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:5fcdca29cf1c96baa38ff52e8ef84c0c6fa1f4c8f9dcbe836ba218b44b307906'
step_id: 'S155'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Remove the unsupported Modelo 193 gastos-total scalar bindings from both revisions and require the official total as explicit manual input while preserving the distinct repeated gasto row export declarations.

## Scope

- `Modelo 193 registry bindings`
- `casilla declarations`
- `validation`
- `live route-ownership gate`

## Changes

- `M` `src/cadrumo/_data/registry/aeat/modelos/193/revisions/2024/bindings/0002-bindings.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/193/revisions/2024/casillas/cdecl.persona-contacto-telefono__cdecl.naturaleza-declarante.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/193/revisions/2025-y-siguientes/bindings/0002-bindings.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/193/revisions/2025-y-siguientes/casillas/cdecl.persona-contacto-telefono__cdecl.naturaleza-declarante.toml`
- `M` `src/cadrumo/domain/calculations/registry/gasto193_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_193_registry.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/domain/calculations/registry/tests/test_modelo_193_registry.py src/cadrumo/application/modelo/tests/test_source_mesh_missing_sources.py` -> `pass`
- `verify:` `uv run ruff check ...` -> `pass`
- `verify:` `rg -n "resolve_gasto193_binding_values|gastos_sum|modelo-193-gastos-total|DEFERRED_SOURCE_KINDS|ACCEPTED_BUCKET_AGGREGATION_SOURCE_KINDS|BUCKET_AGGREGATION_OWNED_SOURCES" src/cadrumo --glob '*.py' --glob '*.toml' --glob '!**/tests/**'` -> `pass`
- `verify:` `uv run python -c "from dev.quality.unused_symbol_coverage import run_gate; ..."` -> `pass` (373 live symbols, 20 orphan tests, scalar resolver absent)
