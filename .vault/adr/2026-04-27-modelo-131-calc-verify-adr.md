---
tags:
  - '#adr'
  - '#modelo-131-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-131-calc-verify-research]]"
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
---



# modelo-131-calc-verify adr: calc-verify-roundtrip | (**status:** `accepted`)

## Problem Statement

Modelo 131 needed the same Tier-L calc-verify coverage as Modelo 130: 2024, 2025, and 2026 annual rulesets; cent-exact worked examples; citation-clean computed casillas; mutation harness coverage; and declaration-import verification evidence.

## Considerations

- The existing M131 implementation is casilla-level verification, not an activity-code module engine.
- RIRPF art. 110 supplies the 2% rates used by casillas 04 and 06.
- Orden HFP/1359/2023, Orden HAC/1347/2024, and Orden HAC/1425/2025 are the annual modules orders for 2024, 2025, and 2026 respectively; the 2026 order keeps the signs, indices, modules, and instructions aligned with 2025.
- The M130 reference ADR and ruleset pattern should be mirrored where the forms share annual-window and citation concerns.
- Live AEAT submission is permanently out of scope.

## Constraints

- Do not introduce source-code delivery-cadence markers.
- Keep extraction scoped to the already complete 15-casilla liquidación block.
- Use real rulesets, formulas, synthetic PDFs, and CliRunner paths; no mocks or skips.
- L1 public anchor is waived because Modelo 131 filings expose private autónomo module data.

## Implementation

Add `modelo_131.2026` as a separate annual ruleset with its own effective window and year-specific formula IDs. Reuse the existing 15-casilla schema and add the 2026 annual modules-order citation at ruleset level. Keep 2024 and 2025 formulas intact, but add per-year worked examples and mutation harness enumeration for the new 2026 nodes.

The rule-delta manifest records the absence of numeric changes for the casilla-level M131 formulas across 2024, 2025, and 2026, citing RIRPF art. 110, Orden EHA/672/2007, Orden HFP/1359/2023, Orden HAC/1347/2024, and Orden HAC/1425/2025.

## Rationale

This keeps the implementation aligned with the local model surface and avoids pretending to implement full activity-code module calculation. It also mirrors the M130 reference pattern: an annual ruleset is cheap, explicit, testable, and future-proof if 2026 or later forms diverge.

## Consequences

- 2026 resolution now works for Modelo 131 without overlapping 2024 or 2025.
- Activity-code modules, territorial reductions, and full module net-yield calculation remain future work.
- Public anchor coverage remains waived until a legally reusable real filing is available.
