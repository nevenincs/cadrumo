---
tags:
  - '#reference'
  - '#modelo-131-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-131-calc-verify-adr]]"
---

# modelo-131 rule-delta reference

This reference records the 2024 to 2025 to 2026 rule trail for Kent's Modelo 131 calc-verify surface.

## Sources

- BOE-A-2007-6820, RD 439/2007, RIRPF art. 110: fixes the Modelo 131 quarterly payment mechanics used here: 4%, 3%, or 2% of objective-estimation net yield depending on employees; 2% of sales/income when no datos-base are available; and 2% of quarterly agricultural, livestock, forestry, or fishing income.
- BOE-A-2007-6032, Orden EHA/672/2007: approves Modelo 131 for IRPF objective-estimation quarterly payments.
- BOE-A-2023-25882, Orden HFP/1359/2023: develops the objective-estimation method for tax year 2024.
- BOE-A-2024-24949, Orden HAC/1347/2024: develops the objective-estimation method for tax year 2025.
- BOE-A-2025-25272, Orden HAC/1425/2025: develops the objective-estimation method for tax year 2026 and states that the 2026 signs, indices, modules, and application instructions are maintained from 2025, with the general 5% module net-yield reduction retained.

## Numeric Delta

| Year | Ruleset | Computed casillas | Parameter | Value | Delta |
| :--- | :--- | :--- | :--- | ---: | :--- |
| 2024 | `modelo_131.2024` | 04, 06, 07, 10, 13, 15 | `modulos.dos_por_ciento` | 0.02 | Baseline from RIRPF art. 110 and the approved M131 form instructions. |
| 2025 | `modelo_131.2025` | 04, 06, 07, 10, 13, 15 | `modulos.dos_por_ciento` | 0.02 | No liquidación-chain change in this repository surface. |
| 2026 | `modelo_131.2026` | 04, 06, 07, 10, 13, 15 | `modulos.dos_por_ciento` | 0.02 | No change; Orden HAC/1425/2025 keeps the 2026 modules and instructions aligned with 2025. |

## Structural Delta

- 2024 and 2025 already shipped the same 15-casilla liquidación block.
- 2026 adds a separate non-overlapping annual ruleset window, `2026-01-01` through `2026-12-31`, with year-specific formula IDs.
- The extractor remains `Modelo131V2025Extractor`; its 15 casillas already cover the liquidación block consumed by the existing synthetic declaración import tests.
- L1 anchor decision: waived for this issue. Public, hash-pinnable Modelo 131 filings are not readily available because the form exposes autónomo activity-level internal module data. The synthetic generator and CLI declaration-import tests are the verification anchor for now.

## Casilla Classification

| Casilla | Classification | Rule |
| :--- | :--- | :--- |
| 01 | user-supplied | Informative module net-yield sum. |
| 02 | user-supplied | Quarterly instalment from datos-base. |
| 03 | user-supplied | Quarterly sales/income when datos-base are unavailable. |
| 04 | computed | `03 * 0.02`. |
| 05 | user-supplied | Agricultural, livestock, forestry, or fishing quarterly income. |
| 06 | computed | `05 * 0.02`. |
| 07 | computed | `02 + 04 + 06`. |
| 08 | user-supplied | Retentions and payments on account. |
| 09 | user-supplied | Prior-year low-yield minoration. |
| 10 | computed | `07 - 08 - 09`. |
| 11 | user-supplied | Prior negative self-assessments. |
| 12 | user-supplied | Primary-residence deduction. |
| 13 | computed | `10 - 11 - 12`. |
| 14 | user-supplied | Prior filing offset for complementaria cases. |
| 15 | computed | `13 - 14`. |

## Out Of Scope

- Activity-code module table modelling is not implemented in this issue. Kent's current ruleset surface starts from casilla-level M131 amounts, not from a full activity-module calculator.
- Territorial reductions, including any La Palma overlay, are not part of the base annual ruleset.
- Live AEAT submission remains forbidden; this work supports local calculation verification and declaration-import review only for Modelo 131.
