---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S12'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

# Model Modelo 145 lifecycle as local payer communication rather than AEAT filing

## Scope

- `registry/aeat/modelos`

## Description

- Model Modelo 145 as a non-filing local payer communication in registry metadata.
- Declare the supported revision periods as communication and variation events rather than filing periods.
- Bind application surfaces to communication, payer delivery, and local export intent only.

## Outcome

- Modelo 145 now loads as `calculation_class = "informative"` and `cadence = "ad_hoc"`.
- The revision application surfaces are exactly `communication`, `payer_delivery`, and `export`.
- The focused foundation test verifies that the registry does not model Modelo 145 as an AEAT filing lifecycle.

## Notes

- Export intent is represented by the application link only; the complete DR145 value-field export layout is still deferred to `P03.S13`.
