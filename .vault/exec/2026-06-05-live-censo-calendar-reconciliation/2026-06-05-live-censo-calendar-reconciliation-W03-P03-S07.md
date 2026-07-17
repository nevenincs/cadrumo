---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S07'
related:
  - "[[2026-06-05-live-censo-calendar-reconciliation-plan]]"
---

# Verify reconciled taxpayer obligations project to actual calendar entries with real filing dates

## Scope

- `src/aeat/application/overview/__init__.py`

## Description

- Verify that the taxpayer facts reconciled from a censo snapshot (S06) project through `projection_for_taxpayer` into a complete taxpayer projection, and that `build_overview_calendar` enumerates the derived Modelo obligations as calendar entries.
- Assert each projected obligation entry carries real filing dates - filing year, AEAT period token, and concrete open/close dates derived from the registry deadline windows - not a bare modelo enumeration.
- Assert the calendar declares `taxpayer_model_declared` true only when the reconciled facts actually establish an obligation, and false when they do not.
- Prove the projection against real censo-snapshot fixtures (the in-test `fact_source` callable), not a live AEAT pull.

## Outcome

- The projection is implemented and verified at HEAD. Reconciling a natural-person censo snapshot with IAE epigraph 763 yields, through `projection_for_taxpayer` -> `build_overview_calendar`, a Modelo 303 calendar entry with `filing_year == 2025`, `period == Period.from_year_and_code(2025, "1T")`, `opens_on == 2025-04-01`, and `closes_on == 2025-04-21` - real filing dates from the registry deadline window.
- `calendar.taxpayer_model_declared` is `True` for the reconciled-obligation case and `False` for the two no-evidence cases (no IAE; non-natural-person identity), so obligations are never silently inferred.
- Fixture-proven, real-behavior (no mocks, no live pull, real `SecureObjectRepository`): `test_censo_sync.py` = 17 passed (-n0). The projection is asserted end-to-end in `test_apply_derives_taxpayer_axes_from_nie_and_iae_for_calendar`; the negative projection cases are `test_apply_does_not_infer_income_category_without_iae` and `test_apply_does_not_infer_income_category_without_natural_person_identity`.

## Notes

- Scope split: this record is the S07 calendar-projection scope only; the paired S06 record covers the reconcile. The pair was originally a single non-standard combined record, now normalized to the vaultspec 1:1 Step-to-exec convention.
- LIVE proof handed to W04: projecting obligations from a live-pulled censo snapshot (rather than a fixture snapshot) and proving live submitted / justificante evidence on the calendar rows is the AEAT-gated scope owned by `W04.P04.S10` and `W04.P04.S11`, both intentionally left open. Nothing here asserts a live pull occurred.
- Where the projection landed: `432a69ac09` (the fixture-backed calendar projection assertions and the negative gates), the `projection_for_taxpayer` -> `build_overview_calendar` path in `src/aeat/application/overview/`, and the sibling W03.P03 calendar-obligation-row exposure steps already closed (S28/S31/S32).
