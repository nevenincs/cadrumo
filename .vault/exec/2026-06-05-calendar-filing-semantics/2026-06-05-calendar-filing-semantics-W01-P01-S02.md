---
tags:
  - '#exec'
  - '#calendar-filing-semantics'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S02'
related:
  - '[[2026-06-05-calendar-filing-semantics-plan]]'
---

# `calendar-filing-semantics` `W01.P01.S02`

Scope: wire CLI calendar storage reads from local Modelo records and calculation observations.

## Description

- Load local `ModeloRecord` catalogue rows for the active bucket.
- Load persisted calculation observations from the active secure store.
- Merge those rows with locally persisted expedientes events before calling the pure calendar builder.
- Render local, AEAT, and justificante states in text calendar output.
- Extend calendar JSON payload schemas for filing evidence and AEAT event evidence fields.

## Outcome

The `app overview calendar` facade remains local-only while exposing the distinction between local application filing and AEAT-submitted evidence.

## Notes

Generic file links are not consumed as AEAT proof. Only promoted `external_evidence`, persisted AEAT live events, and justificante-derived observations participate.
