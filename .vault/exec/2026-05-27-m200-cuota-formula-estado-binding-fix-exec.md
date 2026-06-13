---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'task-183'
related:
  - '[[2026-05-27-schema-hardening-m200-estado-share-binding-repair-exec]]'
  - '[[2026-05-26-cross-domain-continuity-plan]]'
---

# `task-183` M200 cuota engine — formula rewrite + profile field + test migration

Completes Task #183: `DP200014B:00599` cuota ejercicio a ingresar/devolver
was silently emitting 0 for every M200 filing.

## Root cause

`modelo-200-cuota-ejercicio-a-ingresar-devolver` referenced
`{ casilla = "DP200026:00625" }` (porcentaje tributación Estado). That
casilla has `input_kind = "manual"` with no binding and no default. The
formula runtime reads manual casilla inputs from the `inputs` dict via
`inputs.get(casilla.id, _ZERO)` — returning `_ZERO` when the operator
does not explicitly supply it. Result: `(0/100) × cuota_liquida = 0`.

## Fix

Changed the formula expression from `{ casilla = "DP200026:00625" }` to
`{ binding = "modelo-200-2024-profile-tributacion-estado-porcentaje" }`.
The binding resolver reads the value from `TaxpayerProfile.tributacion_estado_porcentaje`
via the profile-binding channel — the same pattern used by
`modelo-200-2024-profile-new-entity-flag` and
`modelo-200-2024-profile-incn-prior-12-months` in the cuota-integra formula.

The casilla `DP200026:00625` remains `input_kind = "manual"` — it is
written to the fichero-BOE export record but is not used by the formula.

An absent binding now raises `RegistryValidationError` (fail-loud) instead
of silently zeroing the cuota.

## Changes

- `formulas.toml` — `modelo-200-cuota-ejercicio-a-ingresar-devolver`
  expression uses `{ binding = "modelo-200-2024-profile-tributacion-estado-porcentaje" }`
- `_models.py` — `TaxpayerProfile.tributacion_estado_porcentaje: Decimal | None = None`
- `test_modelo_200_cuota_integra_lanes.py` — added `_ESTADO_PCT_BINDING` constant,
  updated `_cuota_for` helper, 2 new regression tests:
  `test_cuota_ejercicio_00599_is_non_zero_when_estado_porcentaje_binding_supplied`
  `test_cuota_ejercicio_00599_raises_when_estado_porcentaje_binding_absent`
- 4 other M200 test files — migrated all callsites from
  `inputs["DP200026:00625"] = Decimal("100")` to
  `binding_values["modelo-200-2024-profile-tributacion-estado-porcentaje"] = Decimal("100")`

## Tests

```
uv run --no-sync pytest \
  src/aeat/domain/calculations/registry/test_modelo_200_cuota_integra_lanes.py \
  src/aeat/domain/calculations/registry/test_modelo_200_registry.py \
  src/aeat/domain/calculations/registry/test_modelo_200_temporal_coverage.py \
  src/aeat/domain/calculations/registry/test_modelo_200_tipo_gravamen_dispatch.py \
  src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py -q
```

Result: 56 passed, 2 pre-existing failures unrelated to this change
(`renta-2025-profile-marriage-full-year` binding absent in M100 cross-dep tests).
