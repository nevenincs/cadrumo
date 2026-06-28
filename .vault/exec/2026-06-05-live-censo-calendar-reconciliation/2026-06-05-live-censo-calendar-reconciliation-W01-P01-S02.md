---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S02'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W01.P01.S02 - service and calendar tests

## Scope

Added real-behavior coverage for the censo apply path and calendar enrolment effect.

## Tests Added

- `test_apply_derives_taxpayer_axes_from_nie_and_iae_for_calendar`
  - Captures a real `CensoSnapshot` through `CensoSnapshotService`.
  - Applies it through `CensoSyncService`.
  - Verifies derived source provenance on `taxpayer_type.entity_type` and `taxpayer_type.irpf_income_categories`.
  - Projects the updated `UserProfileRecord` through `projection_for_taxpayer`.
  - Builds an overview calendar and verifies Modelo obligations are enumerated from the derived taxpayer model.
- `test_apply_does_not_infer_income_category_without_iae`
  - Captures a censo snapshot without IAE activity.
  - Verifies only the DNI/NIE-backed natural-person fact is derived.
  - Verifies the calendar remains taxpayer-model undeclared rather than inventing activity obligations.

## Result

The tests exercise the application services directly and do not introduce fakes, mocks, stubs, monkeypatches, skips, or mirrored business logic.
