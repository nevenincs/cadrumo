---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:3158a67d4642ae7982cc675add0036146411ff1951577f982edc9b8ae6f84b1e'
step_id: 'S142'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Restore the festivos TOML hydration boundary so the AEAT business-day deadline shift can load a calendar at all, and record the engine's unshifted close date for an operator ruling

## Scope

- `src/cadrumo/domain/deadlines/festivos.py`

## Changes

- `M` `src/cadrumo/domain/deadlines/festivos.py`
- `verify:` `load_holiday_calendar` for 2024, 2025 and 2026 -> all load (was: all raised)
- `verify:` `pytest src/cadrumo/domain/deadlines/tests -k "festivo or shift or holiday" -n 0 -m ""` -> pass (20)
- `verify:` 843 registry close dates examined, 116 land on a weekend

## Notes

Found while verifying a reported duplication, and larger than the duplication.

`shift_deadline` implements the Ley 39/2015 art. 30.5 business-day rule and has
exactly one production caller, the overview calendar. It could not run. Every
bundled festivos calendar raised on load, because the boundary model whose own
docstring says its job is "coercing the native TOML scalars into the date and
CalendarCCAA field types" carried STRICT_FROZEN_CONFIG -- and strict mode refuses
to turn the authored string "ES-MD" into a CalendarCCAA. The model that exists to
coerce was refusing to.

It failed closed, and then degraded in a way that was recorded but not
alarming. The one caller catches DeadlineValidationError, falls back to the
unshifted date with reason "calendar_unavailable", and logs the exception at
DEBUG.

Corrected after first writing this record: "nothing said so" was too strong.
That reason is carried on every calendar entry and the CLI renders it, so an
operator reading the calendar saw `shift=Calendar unavailable` on every row --
a real signal, with a locale key, that had been there all along. What it was
not is an alert. An identical label on every entry reads as a column heading
rather than a fault, and the dates beside it had silently reverted to the
unshifted legal-text values. The rule was inert for every shipped year, and the
one thing that said so said it uniformly enough to disappear.

Worth separating the two failure shapes, because the fix differs. A swallow that
substitutes a value and surfaces NOTHING is a defect in the handler. This one
surfaced a structural signal that no surface treated as a problem -- closer to
`state_projection.py`'s registry-snapshot handler, which returns a refusal the
caller renders as `registry_ready: false`, except that this one's signal had no
consumer that could act on it.

The three TOML ROW models now carry a frozen, closed, non-strict config -- the
hydration boundary the project rule prescribes, registry TOML free-form and the
loader lifting the typed enum. Holiday and HolidayCalendar, the records these
rows project onto, stay strict.

### Carried forward for an operator ruling

With the calendar loading, a second and separate question becomes answerable, and
it is NOT fixed here because it moves money.

`classify_obligation_status` and the recargo path consume the RAW registry
`closes_on` and never shift it. 116 of 843 registry close dates land on a
weekend, so those dates are raw legal-text dates rather than pre-shifted ones.
Probed: a Modelo 303 window closing Saturday 2026-01-31 shifts to Monday
2026-02-02, and a taxpayer filing on that Monday is classified OVERDUE by the
engine; 2026-01-01 (Año Nuevo) shifts to 2026-01-02 with the same result. The
overview calendar carries the correct `adjusted_closes_on` beside a `status` and
a `recovery` computed from the unadjusted date.

No docstring, comment or ADR states that `closes_on` is deliberately raw and that
consumers must shift it themselves. The direction of the error is
over-declaration -- a false OVERDUE and an overstated recargo -- which is the
direction this codebase's own rules warn is unwatched. Whether AEAT computes the
recargo from the published date or the shifted one is a legal question needing
grounding, so it is recorded rather than decided.
