---
tags:
  - '#reference'
  - '#modelo-200-calc-verify'
date: '2026-04-28'
related:
  - "[[2026-04-28-modelo-200-calc-verify-research]]"
  - "[[2026-04-28-modelo-200-calc-verify-adr]]"
  - "[[2026-04-28-modelo-200-calc-verify-plan]]"
---

# `modelo-200-calc-verify` reference: `2026-200-rule-delta`

## Source Inventory

- BOE-A-2014-12328: Ley 27/2014 LIS, especially arts. 26, 29, 30, 30 bis, 39, and 125.
- BOE-A-2015-7771: Real Decreto 634/2015 RIS, regulatory context for corporate tax and depreciation.
- BOE-A-2025-12818: Orden HAC/657/2025, Modelo 200 for periods initiated in 2024.
- BOE consolidated LIS update through 2026-03-21, checked on 2026-04-28.

## Casilla Inventory

| Casilla | Meaning | Classification | Rule |
| :--- | :--- | :--- | :--- |
| 00547 | BIN compensation | user-supplied | Extracted summary value; derivation deferred because LIS art. 26 needs multi-year state. |
| 00550 | Base before reserve/BIN | user-supplied | Extracted value. |
| 00552 | Base imponible | user-supplied | Input to cuota íntegra. |
| 00558 | Tipo de gravamen | user-supplied | Whole-percent rate printed by M200. |
| 00560 | Cuota íntegra previa | user-supplied | Extracted value. |
| 00562 | Cuota íntegra | computed | `00552 * (00558 / 100)`, LIS arts. 29 and 30. |
| 00582 | Bonificaciones and international double-tax deductions | user-supplied | Extracted value. |
| 00592 | Cuota líquida | user-supplied | Extracted post-deduction value. |
| 00599 | Retenciones e ingresos a cuenta | user-supplied | Extracted value. |
| 00601 | Pago fraccionado 1P | user-supplied | Extracted value. |
| 00603 | Pago fraccionado 2P | user-supplied | Extracted value. |
| 00605 | Pago fraccionado 3P | user-supplied | Extracted value. |
| 00615 | Abono de deducciones | user-supplied | Extracted value. |
| 00619 | Incremento pérdida beneficios fiscales | user-supplied | Extracted value. |
| 00611 | Cuota diferencial | computed | `00592 - 00599 - 00601 - 00603 - 00605`. |
| 00621 | Líquido a ingresar/devolver | computed | `00611 + 00619 - 00615`. |

## Year Delta

| Year | Effective window | Numeric changes | Structural changes |
| :--- | :--- | :--- | :--- |
| 2024 | 2024-01-01 to 2024-12-31 | Existing page-14 arithmetic. General 25 percent, reduced microenterprise 23 percent, startup/new entity 15 percent, and other rate cases handled through printed 00558. | Orden HAC/657/2025 confirms the exercised layout for periods initiated in 2024. |
| 2025 | 2025-01-01 to 2025-12-31 | The ruleset formula body is unchanged. LIS transitional provision 44 applies 21 percent to the first 50,000 euros and 22 percent thereafter for microenterprises, 24 percent for reduced-size entities, plus general 25 percent and new-entity 15 percent. | Separate ruleset ID and effective window. No annual Modelo 200 order for periods initiated in 2025 was published on BOE by 2026-04-28. |
| 2026 | 2026-01-01 to 2026-12-31 | The ruleset formula body is unchanged. LIS transitional provision 44 applies 19 percent to the first 50,000 euros and 21 percent thereafter for microenterprises, 23 percent for reduced-size entities, plus general 25 percent and new-entity 15 percent. | Separate ruleset ID and effective window. The annual order for periods initiated in 2026 is future work. |

## Scope Decisions

Tax-rate split: modeled as user-supplied 00558 for now. The ruleset verifies the arithmetic once the taxpayer-selected rate is printed by AEAT. Full derivation of the rate from taxpayer status is deferred.

Depreciation: deferred. The page-14 extractor has no asset-level amortization inputs, so deriving depreciation would require a broader M200 extraction surface.

Loss carryforward: deferred beyond accepting 00547 as an input. Deriving allowable BIN compensation requires multi-year persistence and taxpayer history.

Pillar 2/minimum tax: deferred. LIS art. 30 bis is important for large groups, but it is outside the Kent-style page-14 summary surface implemented here.

Foral País Vasco/Navarra and Canarias ZEC/RIC: deferred to territorial/special-regime work. The current rulesets cover common-state page-14 arithmetic only.

## L1 Anchor Decision

Waiver. BOE legal/layout sources and L3 synthetic PDFs are used. No public taxpayer declaration PDF was added to the repository.

## Citation and Mutation Status

`aeat audit rulesets citations` reports 100 percent coverage for `modelo_200.2024`, `modelo_200.2025`, and `modelo_200.2026`.

Mutation inventory for each M200 annual ruleset:

| Ruleset | sub_op | compound percent skipped | scalar leaves |
| :--- | ---: | ---: | ---: |
| modelo_200.2024 | 5 | 1 | 1 |
| modelo_200.2025 | 5 | 1 | 1 |
| modelo_200.2026 | 5 | 1 | 1 |
