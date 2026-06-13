---
tags:
  - '#reference'
  - '#calendar-filing-semantics'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-04-calendar-live-filing-integration-reference]]'
  - '[[2026-06-05-calendar-live-operational-hardening-plan]]'
---

# `calendar-filing-semantics` reference: `local readiness versus AEAT submission`

This reference records the implementation surfaces that distinguish the
application's internal filing lifecycle from real-world AEAT submission.

## Local modelo filing records

- `aeat.domain.modelos._filing_record.ModeloRecord` is the durable receipt that a verified calculation revision was marked as the current internal filed answer.
- `ModeloRecord.aeat_accepted` is explicit external acceptance state imported through read-only evidence; it does not mean the application submitted anything.
- `ModeloRecord.external_evidence` carries imported official evidence metadata. `ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF`, `AEAT_CSV_REGISTER`, and `AEAT_LIVE_CAPTURE` are the existing evidence kinds.
- `ModeloRecordCatalogueRepository` loads the encrypted per-profile filing-record catalogue.

## AEAT filed declaration evidence

- `aeat.adapters.outbound.aeat.sede._schema.FiledDeclaracionObservation` is a normalized read-only AEAT filed declaration observation.
- `FiledDeclaracionArtefact.kind` distinguishes `register_row`, `submitted_file`, `declaration_pdf`, and `justificante_pdf`.
- `aeat.application.live.persist_filed_calculation_observation` persists registry-consumable observations with source kind `aeat_sede_justificante`.
- `CalculationObservationRepository.load_observation` and `iter_modelo` expose persisted calculation observations keyed by `(modelo, filing_year, period)`.

## Calendar projection

- `aeat.application.overview.OverviewCalendarEntry` currently models legal deadline rows.
- `OverviewCalendarEvent` models observed local events from live snapshots.
- `calendar_events_from_expedientes_snapshots` turns AEAT declaration-register rows into calendar `filing` events.
- `build_overview_calendar` is pure and accepts preloaded observed events. CLI wiring performs storage reads in `aeat.entrypoints.cli._overview`.

## Correct semantic boundary

Calendar rows need two independent axes:

- Local application filing state: no internal filing record, local verified calculation marked ready/current, or imported external baseline.
- AEAT submission evidence state: not observed, submitted in AEAT register, accepted/imported, or justificante-verified.

The calendar must not collapse either axis into the existing `user_state` legal deadline state.
