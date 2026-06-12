---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-12'
step_id: 'S20'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W05.P05.S20 - cross-period AEAT register provenance enforcement

## Description

- Enforce stamped AEAT register provenance on cross-period source observations.
- Block `aeat_sede_justificante` source observations with non-`ALTA` register status.
- Block source observations whose stamped authenticated identity does not match the taxpayer or expected group member.

## Outcome

Cross-period clean-state now treats encrypted AEAT register provenance as part of official source validity. New persisted `aeat_sede_justificante` observations with `source_metadata` must carry active AEAT status and matching identity before they can satisfy cross-period dependencies.

## Verification

- `uv run --no-sync ruff check src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/_observations_repository.py src/aeat/application/live/_filed_observation_persistence.py src/aeat/application/overview/_calendar.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/calculations/tests/test_observations_repository_roundtrip.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/overview/tests/test_calendar.py` passed.
- `uv run --no-sync pytest src/aeat/application/calculations/tests/test_observations_repository_roundtrip.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/overview/tests/test_calendar.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py -q` passed with 107 tests.

## Notes

Legacy `aeat_sede_justificante` observations without `source_metadata` remain a recorded residual risk because older secure payloads did not persist AEAT register status or authenticated identity.
