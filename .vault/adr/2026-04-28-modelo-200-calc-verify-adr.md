---
tags:
  - '#adr'
  - '#modelo-200-calc-verify'
date: '2026-04-28'
related:
  - "[[2026-04-28-modelo-200-calc-verify-research]]"
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
  - "[[2026-04-28-modelo-180-calc-verify-adr]]"
---

# `modelo-200-calc-verify` adr: `annual page-14 rulesets` | (**status:** `accepted`)

## Problem Statement

Issue 324 requires Modelo 200 calc-verify-roundtrip coverage for 2024, 2025, and 2026. The repository only had `modelo_200.2024`, so 2025 extractor imports were complete but unverifiable. M200 is a corporate income tax form with a much larger full accounting surface than the current formula engine can responsibly derive in one issue.

## Considerations

The existing M200 ruleset is intentionally page-14 scoped. It computes cuota íntegra, cuota diferencial, and líquido a ingresar/devolver from extracted/user-supplied casillas. The LIS supplies the statutory computation for those casillas; the annual Modelo 200 order supplies layout. As of 2026-04-28, BOE has not published the order for periods initiated in 2025, and no order can yet exist for periods initiated in 2026.

M130 and M180 both favor year-specific ruleset IDs and non-overlapping effective windows even when formula bodies are unchanged. That pattern gives registry provenance without pretending there is a new computation.

## Constraints

Live AEAT submission remains forbidden. Verification is limited to `produce -> verify -> export`.

The ruleset must not infer full tax regime eligibility. M200 taxpayers can be general-rate companies, entities under the SME regime, new entities, microenterprises, cooperatives, financial institutions, ZEC entities, or other special regimes. The current form surface already prints the selected rate in casilla 00558, so deriving the rate from entity facts would require additional inputs and validation state.

Depreciation, BIN carryforward derivation, Pillar 2/minimum tax, foral regimes, Canarias ZEC/RIC, and full deduction itemization are out of scope for this ruleset. Their extracted summary casillas can still participate as inputs.

## Implementation

Implement `modelo_200.2025` and `modelo_200.2026` as annual clones of the 2024 page-14 computation with year-specific formula IDs and effective windows. Refactor the 2024 module to expose `_make_casillas` and `_make_formulas`, so the clones reuse the same casilla inventory without duplicating labels.

Computed casillas get year-specific legal citations from LIS arts. 29 and 30, plus RIS context. The 2024 ruleset retains Orden HAC/657/2025 as its layout citation. The 2025 and 2026 rulesets deliberately do not cite unpublished annual orders.

Integration behavior changes from `UNVERIFIABLE` to `VERIFIED` for a complete 2025 synthetic Modelo 200 PDF. A tampered 00621 fixture now produces `NEEDS_REVIEW` with `CORRECTNESS_DIVERGENCE`.

## Rationale

This design satisfies the Tier-L bar for the implemented extraction surface while keeping legal claims accurate. The form already exposes casilla 00558, so rate split coverage belongs in worked examples rather than a premature enum branch. Separate annual rulesets preserve registry correctness and future divergence space.

## Consequences

The rulesets are citation-clean and mutation-visible. Full-form corporate tax derivation remains intentionally deferred. The rule-delta manifest records the annual-order publication gap so future work can revisit layout changes when BOE publishes later M200 orders.
