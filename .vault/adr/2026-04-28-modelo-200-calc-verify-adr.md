---
tags:
  - '#adr'
  - '#modelo-200-calc-verify'
date: '2026-04-28'
modified: '2026-04-28'
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

The ruleset must not infer full tax regime eligibility from the PDF alone. M200 taxpayers can be general-rate companies, entities under the SME regime, new entities, microenterprises, cooperatives, financial institutions, ZEC entities, or other special regimes. The current form surface already prints the selected/effective rate in casilla 00558, so the ruleset verifies that printed value while dedicated statutory helpers derive the rate examples used by tests.

Asset-level depreciation, BIN history, minimum-tax applicability, ZEC base split, and full deduction itemization are explicit inputs to the page-14 verifier. This PR includes strict helpers for the parts that can be derived from those inputs: LIS art. 12 lineal amortization, LIS art. 26 BIN caps, LIS art. 29/DT 44 rate cases including ZEC, and LIS art. 30 bis minimum liquid quota floors. País Vasco and Navarra remain outside the AEAT common-state registry because they are not filed through the AEAT Modelo 200 surface.

## Implementation

Implement `modelo_200.2025` and `modelo_200.2026` as annual clones of the 2024 page-14 computation with year-specific formula IDs and effective windows. Refactor the 2024 module to expose `_make_casillas` and `_make_formulas`, so the clones reuse the same casilla inventory without duplicating labels. Add `modelo_200_corporate_tax.py` for the statutory helper surface used by M200 worked examples.

Computed casillas get year-specific legal citations from LIS arts. 29 and 30, plus RIS context. The 2024 ruleset retains Orden HAC/657/2025 as its layout citation. The 2025 and 2026 rulesets deliberately do not cite unpublished annual orders.

Integration behavior changes from `UNVERIFIABLE` to `VERIFIED` for a complete 2025 synthetic Modelo 200 PDF. A tampered 00621 fixture now produces `NEEDS_REVIEW` with `CORRECTNESS_DIVERGENCE`.

## Rationale

This design satisfies the Tier-L bar for the implemented extraction surface while keeping legal claims accurate. The form already exposes casilla 00558, so the formula ruleset continues to verify the printed rate while the helper module derives the rate, amortization, BIN, ZEC, and minimum-tax examples from explicit facts. Separate annual rulesets preserve registry correctness and future divergence space.

## Consequences

The rulesets are citation-clean and mutation-visible. Corporate-side derivations that can be expressed from explicit facts now have strict helper coverage. The rule-delta manifest records the annual-order publication gap so future work can revisit layout changes when BOE publishes later M200 orders.

## Amendment (2026-05-20): page-14 cuota chain corrected against the AEAT manual

While porting the Modelo 200 page-14 cuota formulas onto the
segment-scoped Liquidacion casillas (the registry-casilla-identity
feature), the shipped registry formula
`modelo-200-cuota-ejercicio-a-ingresar-devolver` was found
tax-incorrect and independently verified against the AEAT Manual
practico de Sociedades 2024 (corpus `aeat-modelo-200-manual-2024`).
The shipped formula computed casilla 00599 as cuota liquida minus
*pagos fraccionados*; the manual (pages 500-501) requires cuota
liquida minus *retenciones*. Pagos fraccionados subtract one step
later, at casilla 00611. This amendment records the authoritative,
manual-grounded page-14 chain that the implementation is corrected to.

- **Cuota integra** — `[00562] = [01330] x [00558] / 100` (manual
  page 362; LIS arts. 29-30). `[01330]` is the base imponible after
  the reserva de nivelacion: `[01330] = [00552] + [01033] - [01034]`
  (manual page 361; LIS art. 105).
- **Cuota del ejercicio a ingresar o a devolver** —
  `[00599] = ([00625] / 100) x ([00592] - [01766] - [01784])` (manual
  pages 500-501; LIS arts. 41, 128). Subtracts *retenciones e ingresos
  a cuenta* (`01766`, `01784`) from the cuota liquida, scaled by the
  Estado share `00625`. The prior shipped formula's subtraction of
  pagos fraccionados here was the defect.
- **Cuota diferencial** — `[00611] = [00599] - ([00601] + [00603] +
  [00605])` (manual page 506; LIS arts. 40-41). The pagos-fraccionados
  relation feeds this step.

The AEAT manual worked liquidacion example (pages 399 and 401,
"Liquidacion del IS 2024 sin tributacion minima") is the external
oracle for the calc-verify test: cuota liquida `00592 = 0`,
retenciones `-20.000` give `00599 = -20.000`; pagos fraccionados
`-10.000` give `00611 = -30.000`. Expected values are AEAT-published,
not author-computed, satisfying the no-tautological-calculation-tests
rule. Decision and scope of this ADR are otherwise unchanged.
