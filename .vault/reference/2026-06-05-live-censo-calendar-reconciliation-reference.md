---
tags:
  - '#reference'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-05-calendar-filing-semantics-plan]]'
---

# `live-censo-calendar-reconciliation` reference

## Current implementation facts

- `aeat config profile censo refresh` calls `CensoSyncService.refresh_censo_from_sede`, which authenticates a live read and fetches G313 through the Sede censo adapter.
- `CensoFactSet` currently parses fiscal address, activity start/end dates, establishment type, elected withholding percent, vivienda office square metres, and IAE epigraph.
- `aeat config profile censo apply` stores G313 facts on `UserProfileRecord` with source `aeat_censo_read`.
- `projection_for_taxpayer` builds the calendar's `TaxpayerProfile` from persisted user-profile facts.
- `build_overview_calendar` refuses to derive legal deadline entries when `taxpayer_model_is_declared` is false. For a natural person this requires `entity_type` plus at least one IRPF income category.
- The active live profile has no captured censo snapshot as of this run. A live G313 refresh reached Cl@ve Movil but timed out waiting for operator completion.

## Gap

The calendar can already consume applied censo activity windows, but censo apply does not derive the taxpayer-model axes required to enumerate Modelo obligations. Therefore a censo refresh/apply alone cannot make the active calendar fully functional.

The defensible bridge is narrow:

- A Spanish DNI/NIE tax id can identify a natural person.
- A live G313 `activities.iae_epigraph` indicates an economic activity and can populate the IRPF income category `actividad_economica`.
- The G313 fields currently parsed do not prove IRPF estimation regime, ROI/OSS, SII/REDEME, large-company status, payer-withholding facts, legal-entity form, or attribution status.

## Required backend behavior

- Censo apply should derive only facts that are legally defensible from captured censo/profile evidence.
- Derived taxpayer facts must carry an explicit censo-derived provenance tag distinct from raw `aeat_censo_read` facts.
- The calendar should remain incomplete when live censo lacks facts needed to derive the taxpayer model; it must not guess missing legal axes.
- Tests must cover both the successful bridge and the refusal path.
