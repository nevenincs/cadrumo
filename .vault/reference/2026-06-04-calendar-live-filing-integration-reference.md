---
tags:
  - '#reference'
  - '#calendar-live-filing-integration'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-calendar-live-filing-integration-research]]'
---

# `calendar-live-filing-integration` reference: `existing implementation surfaces`

This reference records the codebase surfaces used to implement the calendar/live filing integration.

## Calendar projection

- `aeat.application.overview` defines `OverviewCalendarRange`, `OverviewCalendarEntry`, `OverviewCalendar`, `CalendarWarning`, `CalendarCompleteness`, and `build_overview_calendar`.
- `build_overview_calendar` computes schedules by covered year, filters by date intersection and applicability, applies deadline shifts, and sorts entries by close date, modelo, and period.
- `aeat.entrypoints.cli._overview` wires `aeat app overview calendar` to active-profile state and emits `OverviewCalendarResult`.
- `aeat.entrypoints.cli._overview_payloads` defines the JSON schema registered as `overview.calendar`.

## Filed declaration and justificante capture

- `aeat.adapters.outbound.aeat.sede._declarations` drives AEAT's `Consultar declaraciones presentadas` form. Public functions include `walk_declarations_register`, `open_declarations_register`, `capture_declaration`, and conversion helpers for registry observations.
- `Declaracion` rows carry modelo, ejercicio, period, expediente id, status, presentation timestamp, and artefact-link metadata.
- `aeat.application.live` defines `FiledDataListingRow`, `FiledDataListingReport`, `FiledDataCaptureReport`, `list_filed_data`, `capture_filed_data`, `capture_source_filed_data`, and `persist_filed_calculation_observation`.
- `aeat.entrypoints.cli._app_live` exposes `aeat app live filed list`, `capture`, and `capture-sources`.

## Persisted live snapshots

- `aeat.application.live._expedientes` defines `ExpedientesCapture`, `PersistedExpedientesSnapshot`, and `ExpedientesService`.
- `aeat.application.live._notifications` defines `PersistedNotificationsSnapshot` and `NotificationsService`.
- `aeat.adapters.outbound.aeat.sede._notifications` defines `RemoteNotification`, `NotificationsSnapshot`, and the read-only fetch/parse functions.
- Both snapshot services store encrypted bucket-scoped secure objects and expose list/show/latest without contacting AEAT.

## Event/audit context

- `aeat.domain.buckets._event` includes event types for modelo filing lifecycle and live snapshot captures.
- The accepted bucket-event-history ADR states that filing-history repository and live-read snapshot capture events belong in append-only bucket history, but events are not the sole source of relational truth.
