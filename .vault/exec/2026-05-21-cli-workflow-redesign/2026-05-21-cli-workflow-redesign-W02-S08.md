---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S08'
related:
  - '[[2026-05-21-taxpayer-type-applicability-plan]]'
  - '[[2026-05-21-taxpayer-type-applicability-adr]]'
  - '[[2026-05-21-taxpayer-type-applicability-research]]'
---

# `cli-workflow-redesign` `W02.S08`

Derived the overview calendar's tax route, calculation-modelo
selection, and rate/bracket schedule references from the declared
taxpayer model.

- Modified: `src/aeat/application/overview/__init__.py`
- Modified: `src/aeat/application/overview/test_calendar.py`

## Description

`OverviewCalendar` now carries three registry-grounded derivation
fields alongside the filtered filing entries: `tax_route`,
`calculation_selections`, and `rate_schedule_resolutions`. The filing
entries still derive from the existing deadline engine and
applicability filter; the new payload makes the same taxpayer-model
route explicit for consumers that need to inspect which tax branch and
calculation surface were selected.

The calculation selection enumerates only modelos with a positive
applicability verdict and a calculation-bearing registry class, so
informative modelos do not masquerade as calculation work. The rate
schedule derivation reads the central registry authority: natural
persons expose the Modelo 100 IRPF bracket tables and CCAA dispatch refs
for every year covered by the calendar; legal entities expose the Modelo
200 LIS rate parameter selected by `legal_entity_form`, again keyed by
covered filing year; attribution entities and undeclared profiles expose
no cuota rate schedule. Missing yearly rate data degrades to an empty
schedule tuple for that year rather than guessing a tax or revision.

## Tests

- `uv run ruff check src/aeat/application/overview/__init__.py src/aeat/application/overview/test_calendar.py`
  passed.
- `uv run pytest src/aeat/application/overview/test_calendar.py -q`
  passed with 50 tests.
- `uv run pytest src/aeat/application/overview/test_calendar.py src/aeat/application/overview/test_applicability.py src/aeat/application/overview/test_explain.py src/aeat/application/overview/test_agenda.py src/aeat/application/overview/test_backlog.py src/aeat/domain/calculations/registry/test_taxpayer_rate_schedules.py src/aeat/domain/calculations/registry/test_modelo_applicability.py src/aeat/domain/deadlines/test_engine.py -q`
  passed with 170 tests.
- `uv run aeat app registry verify` reported `Verificado=True`.
