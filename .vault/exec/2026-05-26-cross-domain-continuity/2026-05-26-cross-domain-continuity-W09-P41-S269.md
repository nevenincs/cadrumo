---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:f33662cf7620e774796de3d35dbaf7cd1a6781395762bb1f079aff9dd0adb1f0'
step_id: 'S269'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# FU-W10-B oracle-verify M202 2025-2P and 2025-3P closing dates against AEAT calendar and correct if needed

## Scope

- `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/deadline_windows/`

## Description

- Ground the target registry files with `uvx vaultspec-rag search "Modelo 202 2025 2P 3P deadline_windows closes_on October December first twenty days" --type code`.
- Inspect the committed 2025 Modelo 202 deadline windows for `modelo-202-2025-2p` and `modelo-202-2025-3p`.
- Verify the close dates against the AEAT Modelo 202 instructions for 2025 and following, the AEAT pagos-fraccionados plazo page, and the official AEAT 2025 contributor calendar PDF.
- Leave the registry deadline-window TOMLs unchanged because the close dates already match the official calendar evidence.

## Outcome
- `modelo-202-2025-2p` remains correctly registered with `opens_on = 2025-10-01` and `closes_on = 2025-10-20`.
- `modelo-202-2025-3p` remains correctly registered with `opens_on = 2025-12-01` and `closes_on = 2025-12-22`, reflecting the 2025 calendar shift from the twentieth natural day.
- The AEAT Modelo 202 instructions for 2025 and following identify `2/P` as the October payment period and `3/P` as the December payment period, each corresponding to the first twenty natural days of the month.
- The AEAT pagos-fraccionados plazo page independently states that payments are due during the first twenty natural days of April, October, and December.
- The AEAT 2025 contributor calendar confirms Modelo 202/222 October presentation from 1 to 20 October 2025 and December presentation from 1 to 22 December 2025.

## Notes

- No code or registry data change was required for closing dates.
- Source URLs used: https://sede.agenciatributaria.gob.es/Sede/todas-gestiones/impuestos-tasas/impuesto-sobre-sociedades/modelo-202-is-i_____resencia-territorio-fraccionado_/instrucciones/Instrucciones-para-2025.html
- Source URLs used: https://sede.agenciatributaria.gob.es/Sede/impuesto-sobre-sociedades/pagos-fraccionados-impuesto-sobre-sociedades/plazo-presentacion-pagos-fraccionados.html
- Source URLs used: https://sede.agenciatributaria.gob.es/static_files/Sede/Calendario_Contribuyente/Anyos_anteriores/Calendario_del_contribuyente_2025_es_es.pdf
- Residual hardening edge: this step verified `closes_on`, not `payment_cutoff_on`. The registry still has `payment_cutoff_on = 2025-12-15` for `modelo-202-2025-3p`; the general AEAT plazo page says day 15 for domiciliation, while the 2025 calendar domiciliation table appears to show December 2025 presentation with domiciliation through day 17. That source-hierarchy question should be tracked as a separate payment-cutoff audit if the registry expects year-specific holiday/weekend shifts for direct debit cutoffs.
