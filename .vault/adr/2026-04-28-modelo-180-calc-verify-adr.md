---
tags:
  - '#adr'
  - '#modelo-180-calc-verify'
date: '2026-04-28'
modified: '2026-04-28'
related:
  - "[[2026-04-28-modelo-180-calc-verify-research]]"
  - "[[2026-04-27-modelo-115-calc-verify-adr]]"
  - "[[2026-04-27-modelo-123-calc-verify-adr]]"
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
  - "[[2026-04-28-modelo-180-calc-verify-reference]]"
---

# `modelo-180-calc-verify` adr: `annual rental withholding summary` | (**status:** `accepted`)

## Problem Statement

Issue #323 requires Kent to import and verify Modelo 180 declarations for 2024, 2025, and 2026. The prompt frames M180 as an annual aggregator of M111, M115, and M123, but primary AEAT/BOE sources and the issue body define Modelo 180 as the annual summary for rental-withholding returns, with Modelo 115 as the quarterly source.

## Considerations

- BOE-A-2000-21430 and BOE-A-2021-20004 govern the current Modelo 180 form structure and identify the rental-withholding domain.
- RIRPF art. 100.1 keeps the rate at 19 percent; LIRPF arts. 99-101 provide the statutory withholding framework.
- The current extractor surface is the four-casilla summary block, not per-recipient detail rows.
- #437 has not landed, and the M390 ADR is absent in this worktree.
- Foral País Vasco/Navarra handling is out of scope.

## Constraints

Live AEAT submission remains permanently forbidden. Tests must use real formula/extractor/CLI paths and synthetic PDFs, with no mocks or skips. New boundary models must be strict frozen Pydantic v2 models. Expected values must be external-source anchored to BOE/AEAT rules, not copied from ruleset parameters.

## Implementation

Author a 2026 ruleset as a structural clone of the 2025 Modelo 180 summary ruleset with a separate 2026 effective window and 2026 formula id. Register it in the ruleset registry. Add 2024 and 2026 extractor sibling classes for the unchanged summary layout. Add strict frozen Pydantic cumulation records for four Modelo 115-style quarterly sources and derive the annual four-casilla Modelo 180 summary from them, counting unique recipient identities across the year. Extend mutation harness enumeration and Kent CLI integration coverage for 2026.

## Rationale

Approach A is selected, but scoped to Modelo 115. It gives deterministic CI coverage and catches omitted-quarter fixture shape errors without live AEAT access. Approach B is rejected because live access is forbidden and fragile. Approach C is rejected as the primary strategy because it would bypass the PDF/import path; a small Pydantic helper is still used to build the annual casilla map consumed by the real formula engine.

Cent-exact policy: M180 derives casilla 03 from the annual casilla 02 base with terminal two-decimal rounding. Quarterly retenciones remain part of the source record for traceability, but the annual summary follows the ruleset's annual calculation to avoid per-quarter rounding drift.

L1 anchor decision: waiver. No public taxpayer-free Modelo 180 declaration PDF was located. BOE and AEAT instruction pages are the legal/public anchors; L3 synthetic PDFs provide round-trip coverage.

## Consequences

Positive: 2024/2025/2026 ruleset resolution is complete, M180 citation audit remains 100 percent, mutation harness enumeration covers the new 2026 percent node, and Kent CLI import verifies all three years.

Risk: per-recipient records remain outside the extractor surface. This is documented as a scoped summary-block implementation; a future issue can add Pydantic recipient records and row-level extraction once the project has a repeated-record extractor pattern.
