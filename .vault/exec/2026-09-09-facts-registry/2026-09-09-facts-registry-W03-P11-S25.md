---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:205f13b85e4d7465314f123cb0d9d04ddc66603b66a7ba3fc9e82f117502d786'
step_id: 'S25'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# Rewire descendant maternity custody and Madrid windows

## Scope

- `src/cadrumo/domain/contribuyente`

## Changes

- `M` `src/cadrumo/application/modelo/_autonomic_deduccion_advisory.py`
- `M` `src/cadrumo/application/modelo/_minimo_descendientes_advisory.py`
- `M` `src/cadrumo/application/modelo/profile_binding.py`
- `M` `src/cadrumo/application/modelo/tests/test_maternidad_cotizaciones_ceiling.py`
- `M` `src/cadrumo/domain/contribuyente/descendant_guarderia.py`
- `M` `src/cadrumo/domain/contribuyente/descendant_madrid.py`
- `M` `src/cadrumo/domain/contribuyente/descendant_maternity.py`
- `M` `src/cadrumo/domain/contribuyente/descendant_record.py`
- `A` `src/cadrumo/domain/contribuyente/family_fact_context.py`
- `M` `src/cadrumo/domain/contribuyente/family_profile.py`
- `M` `src/cadrumo/domain/contribuyente/family_types.py`
- `A` `src/cadrumo/domain/contribuyente/tests/test_family_fact_context.py`
- `M` `src/cadrumo/domain/contribuyente/tests/test_guarderia_qualifying_meses.py`
- `M` `src/cadrumo/domain/contribuyente/tests/test_incremento_guarderia_prorrateo.py`
- `M` `src/cadrumo/domain/contribuyente/tests/test_madrid_nacimiento_adopcion.py`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/domain/contribuyente/tests/test_family_fact_context.py src/cadrumo/domain/contribuyente/tests/test_guarderia_qualifying_meses.py src/cadrumo/domain/contribuyente/tests/test_incremento_guarderia_prorrateo.py src/cadrumo/domain/contribuyente/tests/test_madrid_nacimiento_adopcion.py src/cadrumo/application/modelo/tests/test_maternidad_cotizaciones_ceiling.py` -> pass
