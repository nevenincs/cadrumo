---
tags:
  - '#plan'
  - '#calendar-live-filing-integration'
date: '2026-06-04'
modified: '2026-06-04'
tier: L2
related:
  - '[[2026-06-04-calendar-live-filing-integration-research]]'
  - '[[2026-06-04-calendar-live-filing-integration-reference]]'
  - '[[2026-06-04-calendar-live-filing-integration-adr]]'
---


<!-- RETIRED: S06, S08 -->

# `calendar-live-filing-integration` `implementation` plan

Integrate persisted live filing/message evidence into the overview calendar and add a bulk filed-declaration capture surface.

## Description

This plan connects the existing calendar, live filed-declaration, expedientes, and notifications surfaces without changing the live-read boundary. Overview remains local-only; live capture remains under `app live filed`.

## Steps

### Phase `P02` - calendar event projection

Add pure overview calendar event models and projection helpers for persisted live-read snapshots.

- [x] `P02.S01` - Extend overview calendar payload schema for events; `src/aeat/entrypoints/cli/_overview_payloads.py`.
- [x] `P02.S02` - Wire local live snapshots into overview calendar CLI output; `src/aeat/entrypoints/cli/_overview.py`.
- [x] `P02.S03` - Add calendar event projection models and helpers; `src/aeat/application/overview/__init__.py`.

### Phase `P01` - bulk filed capture

Add an application service and CLI surface for bulk filed-declaration and justificante capture across registry modelos.

- [x] `P01.S04` - Add bulk filed declaration capture report and service; `src/aeat/application/live/__init__.py`.
- [x] `P01.S05` - Wire filed capture-all CLI command; `src/aeat/entrypoints/cli/_app_live.py`.
- [x] `P01.S07` - Add filed capture-all CLI payloads; `src/aeat/entrypoints/cli/_app_live_payloads.py`.

### Phase `P03` - verification and review

Run focused tests, persist execution records, and audit the implementation before closeout.

- [x] `P03.S09` - Add focused live filed bulk capture tests; `src/aeat/application/live/test_filed_bulk_capture.py`.
- [x] `P03.S10` - Add focused overview calendar event tests; `src/aeat/application/overview/test_calendar.py`.

## Parallelization

Calendar event projection and bulk filed capture can be implemented in parallel after the shared payload shape is clear. CLI wiring depends on the application service and payload models. Verification follows all implementation steps.

## Verification

- Unit tests prove calendar event projection from persisted expedientes and notifications snapshots.
- CLI tests prove `overview calendar` emits events from local persisted snapshots.
- Unit tests prove bulk capture report shape and failure accounting with real application-layer records.
- Targeted pytest passes for overview, live application, live CLI, and payload schema coverage.
- Code review audit records no HIGH or CRITICAL findings.
