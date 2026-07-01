---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S272'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# FU-W09-C S269 verify M202 2025-2P and 2025-3P deadline window closing dates against AEAT oracle

## Scope

- `reviewer could not independently confirm dates without sourcing Orden HAC text`
- `src/aeat/_data/registry/aeat/modelos/202/`

## Description

- Re-run the S269 verification as a second-pass oracle check for the reviewer-blocked row.
- Ground the target registry files with `uvx vaultspec-rag search "Modelo 202 2025 2P 3P deadline_windows closes_on October December first twenty days" --type code`.
- Compare the local `modelo-202-2025-2p` and `modelo-202-2025-3p` close dates against official AEAT Modelo 202 instructions and the AEAT 2025 contributor calendar.
- Treat the AEAT calendar as the date oracle for the 2025 close-date shift.

## Outcome
- The prior reviewer blocker is resolved for closing dates: the AEAT source trail is sufficient without changing registry data.
- `modelo-202-2025-2p` closes on `2025-10-20`, matching the official October 2025 presentation window.
- `modelo-202-2025-3p` closes on `2025-12-22`, matching the official December 2025 presentation window after the non-business-day shift.
- No source or registry correction is required for S269/S272 closing-date scope.

## Notes

- Source URLs used: https://sede.agenciatributaria.gob.es/Sede/todas-gestiones/impuestos-tasas/impuesto-sobre-sociedades/modelo-202-is-i_____resencia-territorio-fraccionado_/instrucciones/Instrucciones-para-2025.html
- Source URLs used: https://sede.agenciatributaria.gob.es/Sede/impuesto-sobre-sociedades/pagos-fraccionados-impuesto-sobre-sociedades/plazo-presentacion-pagos-fraccionados.html
- Source URLs used: https://sede.agenciatributaria.gob.es/static_files/Sede/Calendario_Contribuyente/Anyos_anteriores/Calendario_del_contribuyente_2025_es_es.pdf
- Residual carried from S269: the `payment_cutoff_on` value for `modelo-202-2025-3p` may need a separate source-hierarchy decision because the general AEAT plazo page and the year-specific 2025 calendar differ on whether the December 2025 domiciliation cutoff remains day 15 or shifts to day 17. This row closes only the `closes_on` verification requested by the plan.
