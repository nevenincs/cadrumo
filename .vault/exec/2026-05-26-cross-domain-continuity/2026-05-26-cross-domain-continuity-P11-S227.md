---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
step_id: S227
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W02.P11.S227

## Outcome

Fixed four independent bugs that combined to make M200 (IS anual) and M202
(pagos fraccionados IS) absent from the overview calendar for LEGAL_ENTITY
profiles despite `explain` returning `applicable=true`.

**Bug 1 — `_resolve_profile_fact` missing `taxpayer.entity_type` special case**
`src/aeat/domain/calculations/registry/_schedules.py`

M202's filing schedule declares `field = "taxpayer.entity_type"` but
`TaxpayerProfile` exposes `entity_type` directly with no `.taxpayer`
sub-attribute. The dotted-path walker raised `RegistryValidationError`.
Added a special case mirroring the existing `iva.regime` → `iva_regime`
pattern.

**Bug 2 — `_window_registry_period` unhandled `YYYY-NP` quarterly format**
`src/aeat/domain/deadlines/_engine.py`

M202 windows use `period = "2025-1P"` (pago-fraccionado ordinal) but the
filing schedule lists `periods = ["1P", "2P", "3P"]`. The period filter in
`applicable_filing_schedules` compared `"2025-1P"` against `"1P"` and skipped
the schedule. Added a handler that strips the year prefix for periods ending
with `P`.

**Bug 3 — empty-conditions falsy check in `applicable_filing_schedules`**
`src/aeat/domain/calculations/registry/_schedules.py`

`evaluate_profile_conditions(())` returns `()` (empty tuple, falsy). The
`if evaluate_profile_conditions(...):` guard evaluated `()` as `False`, so
M200's schedule (which has no profile conditions — match-all) was never
selected. Changed to `if evaluate_profile_conditions(...) is not None:`.

**Bug 4 — `covered_years()` missing prior fiscal year**
`src/aeat/application/overview/__init__.py`

M200 has `filing_year=2024` but `opens_on=2025-07-01`. A calendar range of
`2025-01-01` to `2025-12-31` called only `deadline_windows(2025)`, which
filters by `filing_year == 2025`. The M200 2024 window was never fetched.
Expanded `covered_years()` to include `from_date.year - 1`.

**Pre-existing fix — HU locale placeholder**
`src/aeat/locales/hu.yml`

`taxpayer_model_undeclared` carried a self-referencing placeholder key instead
of actual Hungarian text. Fixed so the locale test (`test_undeclared_profile_message_resolves_to_real_localised_text`) passes.

**Test updates**
- `test_schedules.py`: added `test_resolve_profile_fact_taxpayer_entity_type_special_case` regression.
- `test_calendar.py`: added `test_calendar_legal_entity_shows_modelo_202_pagos_fraccionados` and `test_calendar_legal_entity_shows_modelo_200_impuesto_sociedades`; updated `covered_years()` unit tests to reflect expanded year range.
- `test_engine.py`: updated exact-sequence assertions that were over-specified (they asserted a complete sorted obligation list that is now wider because unconditional filing schedules now correctly match all profiles). Tests were rewritten to assert only the obligations they were actually testing (M130/M303 subset membership, counts, etc.).

100 tests across the three modified test modules pass. Ruff clean, pyright 0 errors.

## Commit

`7490eeb67` — S227: fix four bugs causing M200/M202 to be absent from LEGAL_ENTITY calendar
