---
step_id: S23
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S23 — PensionReduccionError

## Outcome

Introduced `PensionReduccionError(CoreValidationError)` in
`src/aeat/application/calculations/_errors.py`. Replaced six bare `ValueError`
raises across two functions in `src/aeat/entrypoints/cli/_modelo.py`:
- Three in `_compute_dt12_reduccion_plan_pensiones` (aportaciones_totales guard,
  gross_rescate guard, aportaciones_pre_2007 guard).
- Three in `_compute_sal_reserva_especial_dotacion` (capital_social guard,
  beneficio_neto guard, reserva_dotada guard).
Each raise now carries a `context` dict with `field` and `value` keys.
Registered `REFUSED_PENSION_REDUCCION_COMPUTATION` in the application error
registry. Locale keys scaffolded in all four present locale files.

## Files touched

- `src/aeat/application/calculations/_errors.py` (PensionReduccionError class)
- `src/aeat/entrypoints/cli/_modelo.py` (import PensionReduccionError, AeatError, get_logger; six raise replacements; _log module logger)
- `src/aeat/core/errors/registry/_application.py` (ErrorCode entry added)
- `src/aeat/locales/en.yml`, `ca.yml`, `es.yml`, `hu.yml` (locale key scaffolded and set)

## Commit

`07378f2c0`
