---
tags:
  - '#adr'
  - '#modelo-123-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - '[[2026-04-27-modelo-123-calc-verify-research]]'
  - '[[2026-04-27-modelo-130-calc-verify-adr]]'
  - '[[2026-04-27-modelo-115-calc-verify-adr]]'
---

# `modelo-123-calc-verify` adr: aggregation-only 2026 rollover | (**status:** `accepted`)

## Problem Statement

Issue #320 requires Modelo 123 calc-verify-roundtrip coverage for 2024,
2025, and 2026. The gap is the missing 2026 ruleset and per-year
round-trip evidence, while preserving the existing cross-tax boundary.

## Considerations

Modelo 123 covers IRPF, IS, and IRNR withholding declarations for capital
income. BOE sources anchor the ordinary IRPF capital-income context:
LIRPF art. 25 defines the income category, LIRPF art. 101.4 sets the
ordinary IRPF capital-income retention rate at 19%, and RIRPF art. 90
applies 19% to the withholding base. That rate is useful for worked
examples but is not sufficient to compute every Modelo 123 row because
the form also covers IS and IRNR rents.

The existing 2025 ruleset already models the stable declaration arithmetic:
`03 = 01 + 02`, `06 = 04 + 05`, `09 = 07 + 08`, and `11 = 09 - 10`.
Casilla `10` is the complementaria offset; casilla `11` is the final
payable amount.

## Constraints

The implementation must keep live AEAT submission out of scope. It must not
claim per-row retention computation where the ruleset verifies only declared
aggregates. Source code must not introduce delivery-wave terminology.

## Implementation

Add `modelo_123.2026` as a structural clone of the 2025 ruleset: same
casillas, formulas, citations, and empty parameter table, with a 2026
effective range. Register it in the ruleset registry.

Extend the generic declaration extractor with `Modelo123V2024Extractor`,
`Modelo123V2025Extractor`, and `Modelo123V2026Extractor`, all sharing the
same 11-casilla liquidación layout.

Add worked examples and mutation-harness registration for 2024/2025/2026.
Extend the Kent CLI integration class so clean synthetic M123 declaration
PDFs for all three years resolve to `VERIFIED`.

## Rationale

This follows the closest landed reference pattern from Modelo 115: year
rollover by structural clone when the legal/computational surface remains
stable. The narrower aggregation-only boundary is retained because M123 is
a cross-tax form and the ruleset cannot safely infer every row's withholding
amount from one IRPF rate.

## Consequences

The registry resolves Modelo 123 for 2024, 2025, and 2026 with
non-overlapping effective ranges. The citation audit covers all computed
M123 casillas. Mutation coverage remains small but explicit: each year has
one `sub_op` node on casilla `11`, no percent-rate nodes, and no bracket
nodes.

L1 public-anchor coverage is waived because public M123 filings would expose
internal withholding data. L3 synthetic round-trip evidence is the accepted
verification path for this Tier-L issue.
