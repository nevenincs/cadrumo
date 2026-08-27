---
tags:
  - '#exec'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:0316afee3c9e128dcb69deec61b3ddd66cba9d7acaf193d9390ad965ab160312'
step_id: 'S17'
related:
  - "[[2026-08-27-registry-dated-validity-plan]]"
---

# Measure the Art. 109 seventy per cent over the base the reglamento names: exclude subvenciones corrientes, subvenciones de capital and indemnizaciones for the agrarian apartados, gate the exemption to the activity classes art. 109 grants it to, and fail closed on a row that does not declare its activity class rather than guessing an exemption for it

## Scope

- `src/cadrumo/core/_concepto_ingreso.py`
- `src/cadrumo/domain/transactions/`
- `src/cadrumo/application/modelo/_art109_activity_income.py and src/cadrumo/_data/registry/aeat/legal/irpf-retencion-actividades.toml`

## Changes

- `M` `src/cadrumo/core/_concepto_ingreso.py`
- `M` `src/cadrumo/core/__init__.py`
- `M` `src/cadrumo/domain/transactions/_volumen_ingresos.py`
- `M` `src/cadrumo/domain/transactions/__init__.py`
- `M` `src/cadrumo/application/modelo/_art109_activity_income.py`
- `M` `src/cadrumo/_data/registry/aeat/legal/irpf-retencion-actividades.toml`
- `A` `src/cadrumo/application/modelo/tests/test_art109_base_excludes_subvenciones.py`
- `verify:` `pytest test_art109_base_excludes_subvenciones.py` -> `pass`
- `verify:` `out-of-tree mutation of the shipped registry, 3 proofs plus control` -> `pass`

## Notes

Reused rather than reinvented. `ConceptoIngreso` and `TipoActividad` already existed
and art. 110.1.c) already paired them; this adds art. 109's own sibling set, predicate
and selectors beside them. The two provisions deliberately do NOT share a set: art. 110
keeps subvenciones corrientes in the base and art. 109.3/109.4 take them out, so one
shared set would get exactly one provision wrong. A test pins the divergence to exactly
SUBVENCION_CORRIENTE so a later merge of the two reds.

The activity selectors are declared under art. 109 rather than borrowing the art. 95
retencion partitions they currently coincide with, following the reasoning the art. 110
selector already records: those partition retention RATES, and this exemption's scope
must not move if a rate partition is re-cut.

The A04-with-A05 profesional grouping follows the art. 95 partition this registry
already grounds. It is an agent tax review and the parameter says so in reviewed_by;
the operator should re-stamp it.

Seventeen tests fail in the affected run. All seventeen are in repo-wide core gates
(source-connectivity, storage-liveness, period-string, clock-seam, modelo-string,
persisted-version, external-constants) and every failing module was already failing in
the pre-change sweep recorded earlier in this campaign. None is in the art. 109,
transactions, concepto or volumen surface this step touched.
