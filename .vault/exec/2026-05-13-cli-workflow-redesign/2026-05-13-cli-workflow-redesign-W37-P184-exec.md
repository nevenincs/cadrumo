---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W37.P184'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-festivos-deadline-shift-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W37.P184`

Real-behaviour verification. Thirty BOE-anchored tests cover the
calendar loader, the business-day predicate, the next-business-day
walk, the deadline-shift service, and the Modelo 369 exception.

- Created: `src/aeat/domain/deadlines/test_festivos.py`

## Description

The test suite grounds every expected value in an external
authority — either BOE-A-2024-22011 (the 2025 fiestas-laborales
Resolución cited inline at the top of the file), the AEAT Calendario
del Contribuyente shift rule, or a structural / wiring / error-path
property. No test computes the expected adjusted date by re-applying
the same shift formula to a freshly-invented date — that would be a
tautological calculation test forbidden by the project rule
`.claude/rules/no-tautological-calculation-tests.md`.

Suite breakdown:

- Calendar loading (5 tests): the 2025 calendar TOML cites BOE-A-
  2024-22011; national-only and CCAA-only buckets stay disjoint;
  unknown years raise `DeadlineValidationError`; the `lru_cache`
  returns identical instances on repeat calls.
- `is_business_day` predicate (6 tests): weekend Saturday / Sunday,
  national Friday-holiday (2025-04-18 Viernes Santo), CCAA-only
  Diada in ES-CT versus ES-MD, plain weekday, and the
  `ccaa_code=None` degraded mode.
- `next_business_day` walk (4 tests): identity when already a
  business day, weekend skip to Monday, holiday + weekend skip, and
  a bounded-walk error path when the calendar is malformed.
- `shift_deadline` service (8 tests): no shift on a plain weekday,
  Saturday → Monday shift, Sunday → Monday shift, national-holiday
  shift with `holiday_refs` populated, CCAA-only shift in the
  matching CCAA, no shift for the same CCAA-only holiday in a
  different CCAA, the Modelo 369 exception (`shifted=False` even
  when the close date falls on a Sunday), and the bounded shift_days
  property.
- Pydantic schema validation (5 tests): `strict=True` rejects ints
  posing as bools and date-shaped strings; `extra="forbid"` rejects
  unknown keys; `frozen=True` rejects post-construction mutation.
- Boundary regression guards (2 tests): the no-parallel-festivos
  test and the no-hardcoded-festivos-table-in-CLI test described in
  P182 / P183.

Result: 30 / 30 festivos tests pass. The full
`src/aeat/domain/deadlines/` suite remains green at 81 / 81 after
the additions, so no incidental regression was introduced into the
existing `DeadlineEngine` paths.

Closed plan rows: `W37.P184.S1099`, `W37.P184.S1100`,
`W37.P184.S1101`, `W37.P184.S1102`, `W37.P184.S1103`,
`W37.P184.S1104`.

## Tests

`uv run --no-sync pytest src/aeat/domain/deadlines/ -q` — 81 / 81
pass.
