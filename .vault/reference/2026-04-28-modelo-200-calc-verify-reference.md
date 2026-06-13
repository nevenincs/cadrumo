---
tags:
  - '#reference'
  - '#modelo-200-calc-verify'
date: '2026-04-28'
modified: '2026-04-28'
related:
  - "[[2026-04-28-modelo-200-calc-verify-research]]"
  - "[[2026-04-28-modelo-200-calc-verify-adr]]"
  - "[[2026-04-28-modelo-200-calc-verify-plan]]"
---

# `modelo-200-calc-verify` reference: `2026-200-rule-delta`

## Source Inventory

- BOE-A-2014-12328: Ley 27/2014 LIS, especially arts. 26, 29, 30, 30 bis, 39, and 125.
- BOE-A-2015-7771: Real Decreto 634/2015 RIS, regulatory context for corporate tax and depreciation.
- BOE-A-1994-15794: Ley 19/1994 REF Canarias, arts. 43-44 for ZEC rate/base handling.
- BOE-A-2025-12818: Orden HAC/657/2025, Modelo 200 for periods initiated in 2024.
- BOE consolidated LIS update through 2026-03-21, checked on 2026-04-28.

## Casilla Inventory

| Casilla | Meaning | Classification | Rule |
| :--- | :--- | :--- | :--- |
| 00547 | BIN compensation | user-supplied | Extracted summary value; `modelo_200_bin_compensation_cap` derives the statutory LIS art. 26 cap from base, pending BIN, period length, and new-entity/extinction flags. |
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

## In-Scope Statutory Helpers

Tax-rate split: `modelo_200_tax_due` and `modelo_200_effective_rate` model the common-state 2024-2026 regimes used by worked examples: general 25 percent, new entity 15 percent, financial/hydrocarbon 30 percent, microenterprise tiering, reduced-size transitional rates, and ZEC 4 percent on ZEC-eligible base. The page-14 rulesets still verify the printed casilla 00558 because M200 itself prints the selected/effective whole-percent rate.

Depreciation: `Modelo200DepreciableAsset` and `modelo_200_max_lineal_amortization` derive representative asset-level amortization from the shared LIS art. 12.1.a lineal table. The page-14 extractor does not expose asset rows, so amortization remains an input to the extracted page-14 declaration, but the statutory derivation is covered by strict tests.

Loss carryforward: `modelo_200_bin_compensation_cap` implements LIS art. 26's 70 percent cap, the 1,000,000 EUR floor prorated for short periods, and the new-entity/extinction exceptions. Pending BIN provenance remains taxpayer-history input; the deductible cap is no longer only prose.

Minimum liquid quota: `modelo_200_minimum_liquid_quota` implements the LIS art. 30 bis floor for taxpayers to whom the minimum tax applies, including 10 percent for new entities, 18 percent for financial/hydrocarbon entities, scaled microenterprise/reduced-size floors, and ZEC base exclusion.

Territorial scope: Canarias ZEC is represented for rate/effective-rate and minimum-tax base exclusion. País Vasco and Navarra are not AEAT common-state Modelo 200 filings; this PR keeps them out of the AEAT ruleset registry rather than treating them as missing common-state formulas.

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
