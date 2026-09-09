---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:e0054cc03617b0dc89c77f7230a57ae47dd19ee143bd9dd15fb9ad714d47957b'
step_id: 'S53'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# Rewire deadline notification amendment and foreign-asset facts

## Scope

- `src/cadrumo/domain/deadlines and src/cadrumo/core`

## Changes

- `A` `src/cadrumo/domain/deadlines/fact_context.py`
- `M` `src/cadrumo/domain/deadlines/models.py`
- `M` `src/cadrumo/core/notificacion_estado_servicio.py`
- `M` `src/cadrumo/application/overview/status_report.py`
- `M` `src/cadrumo/application/overview/calendar.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_work_lifecycle_cli.py`
- `M` `src/cadrumo/domain/deadlines/tests/test_taxpayer_model.py`
- `M` `src/cadrumo/core/tests/test_notificacion_estado_servicio.py`
- `verify:` `uv run --no-sync pytest -n 0 src/cadrumo/domain/deadlines/tests/test_taxpayer_model.py::TestMultiplePagadoresObligation src/cadrumo/domain/deadlines/tests/test_taxpayer_model.py::TestMultiplePagadoresReducedLimitSchedule src/cadrumo/domain/deadlines/tests/test_taxpayer_model.py::TestMultiplePagadoresObligationWithTotalIncome src/cadrumo/core/tests/test_notificacion_estado_servicio.py src/cadrumo/application/overview/tests/test_calendar_notificacion_estado_servicio.py -q` -> `pass`
- `verify:` `uv run --no-sync pytest -n 0 src/cadrumo/application/overview/tests/test_calendar.py::test_invalid_pagadores_values_are_debug_logged_without_raw_value -q` -> `pass`
- `verify:` `uv run --no-sync python -m compileall -q src/cadrumo/domain/deadlines/fact_context.py src/cadrumo/domain/deadlines/models.py src/cadrumo/core/notificacion_estado_servicio.py src/cadrumo/application/overview/status_report.py src/cadrumo/application/overview/calendar.py src/cadrumo/entrypoints/cli/_modelo_work_lifecycle_cli.py` -> `pass`

## Notes

No governed amendment-regime or foreign-asset provider fact exists, so their typed domain projections remain unchanged. Holiday event facts have no calendar-publication sentinel, so an absent event cannot distinguish a non-holiday from an unpublished year; the business-day facade remains unchanged pending that provider-contract addition.
