---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:77f1799c74ac6ff09782e7eb0c0db400914e124be3fd0938ba162263d300a013'
step_id: 'S330'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the Modelo 232 literal-set duplicate detector and raw type-hint assertions

## Scope

- `Modelo 232 singularity gate`
- `direct hydration and registry behavior`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_modelo_232_codigo_singularity.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/domain/modelos/tests/test_m232_row_capacity.py src/cadrumo/domain/calculations/registry/tests/test_modelo_232_registry.py src/cadrumo/application/calculations/tests/test_modelo_232_operaciones_vinculadas_fidelity.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

Exact remeasurement reports the campaign's remaining live signal: 36 unreachable modules and 278 unused symbols.
