---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-12'
step_id: 'S18'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W05.P05.S18 - active AEAT status for official filed-observation history

## Description

- Refuse direct persistence of non-`ALTA` filed AEAT observations into calculation history.
- Rank bulk filed-observation persistence by active AEAT status before timestamp and expediente id.
- Apply the same active-status ranking to IVA compensation history persistence.
- Add live application tests proving non-`ALTA` observations cannot become official calculation or IVA history.

## Outcome

Live filed-observation persistence now shares the active-status boundary used by declaration selection and calendar projection. A later `BAJA` or otherwise non-current AEAT register row can no longer overwrite an older `ALTA` row in official `aeat_sede_justificante` calculation history or IVA compensation history.

This protects cross-period filing gates from using stale or cancelled AEAT register rows as official source data.

## Notes

Verification passed:

- `uv run ruff check src/aeat/application/live/_filed_observation_persistence.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py`
- `uv run pytest src/aeat/application/live/tests/test_filed_capture_calculation_history.py -q` passed with 13 tests.

The live Modelo 036/G313 censo-derived obligation proof remains open until a matching taxpayer profile authenticates successfully.
