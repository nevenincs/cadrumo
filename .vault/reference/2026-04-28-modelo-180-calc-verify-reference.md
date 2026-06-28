---
tags:
  - '#reference'
  - '#modelo-180-calc-verify'
date: '2026-04-28'
modified: '2026-04-28'
related:
  - "[[2026-04-28-modelo-180-calc-verify-research]]"
  - "[[2026-04-28-modelo-180-calc-verify-adr]]"
  - "[[2026-04-28-modelo-180-calc-verify-plan]]"
---

# `modelo-180-calc-verify` reference: `2026-180-rule-delta`

## Source Inventory

- BOE-A-2000-21430: Orden de 20 de noviembre de 2000 approving Modelos 115 and 180 and the Modelo 180 layouts.
- BOE-A-2021-20004: Orden HFP/1351/2021 modifying the Modelo 180 order and maintaining the rental-withholding summary structure.
- BOE-A-2007-6820: RD 439/2007 RIRPF art. 100.1, 19 percent withholding on urban property leases.
- BOE-A-2006-20764: LIRPF arts. 99-101, withholding obligation and statutory framework.
- AEAT Modelo 180 help and AEAT activities-folleto: operational confirmation that Modelo 115 is quarterly and Modelo 180 is the annual summary.

## Casilla Inventory

| Casilla | Meaning | Classification | Rule |
| :--- | :--- | :--- | :--- |
| 01 | Total perceptores | user-supplied | Sum of annual recipient count from Modelo 115-style quarterly sources. |
| 02 | Total base retencion | user-supplied | Sum of annual rental-withholding base. |
| 03 | Total retenciones | computed | 19 percent of casilla 02, RIRPF art. 100.1. |
| 04 | Total ingresos a cuenta | user-supplied | Sum of annual in-kind payments on account. |

## Year Delta

| Year | Effective window | Numeric changes | Structural changes |
| :--- | :--- | :--- | :--- |
| 2024 | 2024-01-01 to 2024-12-31 | None; 19 percent rate. | Four-casilla summary block. |
| 2025 | 2025-01-01 to 2025-12-31 | None; 19 percent rate. | Four-casilla summary block. |
| 2026 | 2026-01-01 to 2026-12-31 | None; 19 percent rate. | Four-casilla summary block, separately registered. |

No 2024 -> 2025 or 2025 -> 2026 numeric delta was found in the consulted BOE sources. BOE-A-2007-6820 RIRPF art. 100.1 remains the active rate source.

## Cumulation Rules

Modelo 180 is modeled as the annual summary of four Modelo 115-style quarterly sources:

| M180 casilla | Quarterly source |
| :--- | :--- |
| 01 | Count of unique recipient identities across 1T, 2T, 3T, 4T. Quarterly M115 casilla 01 values are validated against fixture recipient ids, not summed blindly. |
| 02 | Sum of M115 casilla 02 across 1T, 2T, 3T, 4T. |
| 03 | Derived as 19 percent of annual M180 casilla 02. Quarterly M115 casilla 03 values remain trace inputs but are not summed as the authoritative computed value because per-quarter rounding can drift from annual-form rounding. |
| 04 | Sum of M115 casilla 04 across 1T, 2T, 3T, 4T. |

The implemented helper requires exactly four quarter records and per-recipient identities so recurring landlords count once annually. M111 and M123 are not Modelo 180 inputs under the consulted sources; their annual informative summaries are separate modelos.

## Per-Recipient Detail

Modelo 180 has recipient/property detail in the official layout, but the current extractor surface is the four-casilla summary block. This issue records per-recipient repeated rows as future scope rather than modeling synthetic row extraction without a local repeated-record parser pattern.

## L1 Anchor Decision

Waiver. No public, taxpayer-free Modelo 180 declaration PDF was found. BOE layout/instruction pages and AEAT help pages are used as public anchors; L3 synthetic PDFs cover the import path.

## Citation and Mutation Status

`aeat audit rulesets citations` reports 100 percent coverage for `modelo_180.2024`, `modelo_180.2025`, and `modelo_180.2026`. Mutation harness enumeration includes one percent-rate parameter node for each M180 year and no sub-op, bracket, or scalar nodes.
