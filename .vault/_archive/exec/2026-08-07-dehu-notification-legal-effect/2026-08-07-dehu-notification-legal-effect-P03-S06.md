---
tags:
  - '#exec'
  - '#dehu-notification-legal-effect'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:9b54a512e2c4cc0d4b377b8954f925f8522446a85a6f0f53104a5e37b936a3db'
step_id: 'S06'
related:
  - "[[2026-08-07-dehu-notification-legal-effect-plan]]"
---

# Add a typed notificacion_estado_servicio field, typed NotificacionEstadoServicio or None, to OverviewCalendarEvent, and compute it per row in calendar_events_from_notification_snapshots from fecha_notificacion and leida against an explicit as_of parameter threaded from the caller, never an inline date.today call, then add a projection test proving a synthetic ten-day-lapsed row computes RECHAZO_TACITO

## Scope

- `src/cadrumo/application/overview/_calendar.py`
- `src/cadrumo/application/overview/tests/`

## Description

- Add the typed service-state field to the overview calendar event, documented
  as populated only for message rows projected from notification snapshots,
  where a delivery date and an access flag exist to compute it from.
- Compute it per row in the notification projection against a required
  keyword-only `as_of`, so a projection over stored snapshots is reproducible
  rather than dependent on the day it runs.
- Thread `as_of` from the clock boundary that already owns it: the two overview
  calendar command bodies pass the Madrid-today they already compute, through
  the evidence loader and the fan-out builder, with no inline clock read added
  anywhere below the command.
- Sweep every existing call site of the two widened signatures in the same
  change, since the new keyword is required rather than defaulted.

## Outcome

The field is on the event model, the projection populates it, and `as_of` is a
required keyword on both the notification projection and the fan-out builder.
The single-profile command computes the date once and reuses it for both the
event projection and the calendar build, replacing a second clock read that
could previously have straddled midnight and dated the two halves differently.

Eight call sites were swept: four in the procedural-category test module, three
in the calendar test module, and one in the CLI degradation test. Each was given
a fixture date inside the window, so the new axis cannot influence assertions
those modules make about other concerns.

## Verification

    uv run --no-sync pytest src/cadrumo/application/overview/tests/ -n0 -q
    240 passed in 34.50s

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_overview_calendar_degradation.py -n0 -q
    3 passed in 4.38s

    uv run --no-sync ruff check src/cadrumo/application/overview/ src/cadrumo/entrypoints/cli/_overview.py src/cadrumo/entrypoints/cli/_overview_evidence.py src/cadrumo/entrypoints/cli/tests/test_overview_calendar_degradation.py
    All checks passed!

    uv run --no-sync python -m dev.docs.apidocs scaffold --check
    Stub tree is conformant. No drift detected.

The projection suite includes an assertion that the same stored snapshot yields
different states for two different `as_of` values. That is the property making
the projection reproducible: had the builder read a clock instead of the
argument, both calls would agree and the assertion would fail whichever state
they agreed on.

## Notes

Two peer files were dirty in the entrypoints package while this Step ran and
were excluded from its commit by explicit pathspec. The commit carries eight
files, all of them this Step's.
