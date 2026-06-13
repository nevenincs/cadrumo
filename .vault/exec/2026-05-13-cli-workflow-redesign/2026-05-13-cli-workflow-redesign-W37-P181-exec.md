---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W37.P181'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-festivos-deadline-shift-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W37.P181`

Landed the backend implementation phase for the Spanish business-day
calendar and the AEAT deadline-shift service.

- Created: `src/aeat/domain/deadlines/_festivos.py`
- Created: `registry/aeat/calendars/festivos-2024.toml`
- Created: `registry/aeat/calendars/festivos-2025.toml`
- Created: `registry/aeat/calendars/festivos-2026.toml`
- Modified: `src/aeat/domain/deadlines/__init__.py`

## Description

Implemented a pure-domain calendar substrate that owns the legally
binding shift rule from the AEAT Calendario del Contribuyente
(*"Vencimientos en días inhábiles, sábados o festivos"*). The
substrate sits in `aeat.domain.deadlines` and never reaches into
the CLI or the storage layer.

Public surface added to `aeat.domain.deadlines`:

- `CCAA` — a `StrEnum` of the nineteen autonomous communities and
  cities, keyed by ISO 3166-2:ES codes. Used to scope CCAA-level
  holiday lookups by the taxpayer's domicilio fiscal.
- `HolidayJurisdiction` — `NATIONAL` and `CCAA`. Municipal holidays
  are intentionally excluded because AEAT does not shift filing
  deadlines on them.
- `Holiday`, `HolidayCalendar` — Pydantic v2 frozen models with
  `strict=True` and `extra="forbid"` carrying the BOE-cited annual
  calendar.
- `DeadlineShift` — the structured record returned by the shift
  service: original close date, adjusted close date, the boolean
  predicate `shifted`, non-negative `shift_days`, a `shift_reason`
  identifier, the jurisdictions whose holidays applied, and the
  citation refs.
- `load_holiday_calendar(year)` — loader for
  `registry/aeat/calendars/festivos-{year}.toml`. Wrapped in
  `lru_cache(maxsize=64)` so repeat callers in the same process get
  identity-equal calendars. Raises `DeadlineValidationError` when
  the requested year has no registered TOML.
- `is_business_day(date, *, calendar, ccaa_code)` — predicate. When
  `ccaa_code` is `None` the predicate degrades to national-only
  evaluation, the safe fall-back for callers without tax-residence
  data.
- `next_business_day(date, *, calendar, ccaa_code)` — bounded walk
  (max fourteen days) that returns the next día hábil.
- `shift_deadline(original_close_date, *, modelo, ccaa_code,
  calendar=None)` — the user-facing shift service. Honours the
  modelo-specific exception list, threads through the holiday refs,
  and produces an explainable `DeadlineShift` record.

Modelo-specific exception list:

- `MODELOS_WITHOUT_SHIFT: tuple[str, ...] = ("369",)` — the OSS /
  IOSS one-stop-shop modelo. Its deadline is governed by the EU
  Council Directive's harmonised cutoff and AEAT cannot lengthen the
  window unilaterally. New modelos that join this list land as data,
  not as a fork inside `shift_deadline`.

Calendar TOMLs:

- `festivos-2024.toml` cites BOE-A-2023-21965.
- `festivos-2025.toml` cites BOE-A-2024-22011.
- `festivos-2026.toml` carries the high-confidence national core
  plus the bootstrap CCAA entries (Madrid, Cataluña, Andalucía,
  Comunitat Valenciana) for the regional fixed dates already
  scheduled by the autonomous gazettes.

Errors:

- `DeadlineValidationError` (already in
  `aeat.core.errors.registry._domain`) is the surface for missing
  calendars, missing CCAA codes for CCAA-only holidays, and
  malformed records. No new error code was added — the existing
  registry entry covers the festivos failure modes.

Closed plan rows: `W37.P181.S1081`, `W37.P181.S1082`,
`W37.P181.S1083`, `W37.P181.S1084`, `W37.P181.S1085`,
`W37.P181.S1086`.

## Tests

`uv run --no-sync pytest src/aeat/domain/deadlines/test_festivos.py -q`
— 30 / 30 pass.

Full deadlines suite (81 tests) remains green after the festivos
additions.
