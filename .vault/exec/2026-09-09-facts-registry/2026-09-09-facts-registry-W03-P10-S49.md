---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:60478ad7e8fdce44697fa926b37bad52d68c33f2feca0a9886110eb174d6432a'
step_id: 'S49'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---


# Rewire Modelo 202 and modelo classification consumers

## Scope

- `src/cadrumo/domain/calculations/registry/applicability_modelo202.py and src/cadrumo/application/aggregation/_service.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/applicability_modelo202.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_200_cuota_integra_lanes.py`
- `M` `src/cadrumo/application/aggregation/_service.py`
- `M` `src/cadrumo/application/aggregation/_modelo_bindings_retenciones.py`
- `M` `src/cadrumo/application/aggregation/tests/test_terminal_preconditions.py`
- `M` `src/cadrumo/domain/transactions/tipo_actividad_partitions.py`
- `M` `src/cadrumo/domain/transactions/tests/test_tipo_actividad_partitions.py`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W03-P10-S49.md`
- `verify:` `uv run pytest src/cadrumo/application/aggregation/tests/test_per_modelo_service.py src/cadrumo/application/aggregation/tests/test_terminal_preconditions.py src/cadrumo/domain/transactions/tests/test_tipo_actividad_partitions.py -q` -> `pass`
- `verify:` `uv run pytest src/cadrumo/domain/calculations/registry/tests/test_modelo_200_cuota_integra_lanes.py -q` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/domain/calculations/registry/applicability_modelo202.py src/cadrumo/domain/transactions/tipo_actividad_partitions.py src/cadrumo/application/aggregation/_service.py src/cadrumo/application/aggregation/_modelo_bindings_retenciones.py src/cadrumo/domain/calculations/registry/tests/test_modelo_200_cuota_integra_lanes.py src/cadrumo/domain/transactions/tests/test_tipo_actividad_partitions.py src/cadrumo/application/aggregation/tests/test_terminal_preconditions.py` -> `pass`
