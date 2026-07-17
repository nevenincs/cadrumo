---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S363'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R9-ROBERTO-HIGH model property use_type as first-class enum on Transaction or rental input model

## Scope

- `closed by c30e1b7f0: finca UseType now includes VIVIENDA_TURISTICA alongside VIVIENDA_ARRENDADA`
- `LOCAL_COMERCIAL`
- `VIVIENDA_HABITUAL`
- `OTRO_INMUEBLE_NO_AFECTO`
- `and VIVIENDA_DESOCUPADA`
- `and the Art. 23.2 reduction resolver refuses every non-VIVIENDA_ARRENDADA use type instead of allowing a vivienda turística or commercial premise to claim the vivienda-permanente reduction`
- `verified by 30 focused fincas tier-resolver tests on 2026-07-01`
- `src/aeat/domain/fincas/`

## Description

- Reconciled the finca use-type correction to the plan's cited landing.
- Confirmed `c30e1b7f0` supplied the implementation and focused verification.
- Added this per-step execution record without changing production sources.

## Outcome

The plan's explicit landing evidence supports the checked row. This record restores the one-Step, one-record traceability edge.

## Notes

The original plan row records the legal and test coverage.
