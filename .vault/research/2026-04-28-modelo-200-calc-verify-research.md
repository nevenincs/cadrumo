---
tags:
  - '#research'
  - '#modelo-200-calc-verify'
date: '2026-04-28'
modified: '2026-04-28'
related:
  - "[[2026-04-27-modelo-130-calc-verify-research]]"
  - "[[2026-04-28-modelo-180-calc-verify-research]]"
---

# `modelo-200-calc-verify` research: `2024-2026 ruleset and roundtrip`

This research covers Modelo 200, the annual Impuesto sobre Sociedades self-assessment for corporate taxpayers. The existing implementation already contained a 2024 page-14 liquidación ruleset and a v2025 extractor for the five-digit casilla layout. The work needed for issue 324 is to close the annual registration gap for 2025 and 2026 without expanding into the full accounting statement or special-regime annexes.

## Findings

The implemented M200 ruleset surface is the invariant liquidación chain:

| Casilla | Classification | Rule |
| :--- | :--- | :--- |
| 00547 | user-supplied | BIN compensation, retained as extracted input. |
| 00550 | user-supplied | Base before reserve/carryforward adjustments. |
| 00552 | user-supplied | Base imponible used by the page-14 arithmetic. |
| 00558 | user-supplied | Applicable tax rate printed as a whole-percent value. |
| 00560 | user-supplied | Pre-casilla cuota field, retained as extracted input. |
| 00562 | computed | `00552 * (00558 / 100)`, LIS arts. 29 and 30. |
| 00582 | user-supplied | Bonificaciones and international double-tax deductions. |
| 00592 | user-supplied | Cuota líquida after taxpayer-specific deductions. |
| 00599 | user-supplied | Withholdings and payments on account. |
| 00601 | user-supplied | First corporate instalment payment. |
| 00603 | user-supplied | Second corporate instalment payment. |
| 00605 | user-supplied | Third corporate instalment payment. |
| 00615 | user-supplied | Refundable/monetized deductions. |
| 00619 | user-supplied | Increment for lost tax benefits. |
| 00611 | computed | `00592 - 00599 - 00601 - 00603 - 00605`. |
| 00621 | computed | `00611 + 00619 - 00615`. |

Primary BOE sources checked:

- BOE-A-2014-12328, Ley 27/2014 LIS. Article 29 defines the general 25 percent rate, the steady-state microenterprise bands, reduced-size-entity treatment, and the 15 percent new-entity/startup rate. Transitional provision 44 sets the 2025 rates at 21/22 percent for microenterprises and 24 percent for reduced-size entities, and the 2026 rates at 19/21 percent and 23 percent. Article 30 defines cuota íntegra as applying the tax rate to the taxable base and cuota líquida after deductions. Article 26 defines BIN carryforward limits. Article 30 bis defines the minimum-tax rule for large taxpayers.
- BOE-A-2015-7771, Real Decreto 634/2015 RIS. It remains relevant for depreciation context and regulatory development, but the current ruleset does not compute depreciation tables.
- BOE-A-2025-12818, Orden HAC/657/2025. This approves the Modelo 200 for periods initiated in 2024 and confirms the page-14 layout used by the current extractor.
- BOE consolidated LIS as updated through 2026-03-21. The 2025 annual Modelo 200 order for periods initiated in 2025 was not found on BOE as of 2026-04-28, and a 2026 annual order is necessarily not yet available.

The closest implementation patterns are Modelo 130 and Modelo 180. Modelo 130 shows per-year rulesets with separate effective windows and mutation fixtures. Modelo 180 shows annual form cloning when the statutory computation is unchanged. M200 follows the annual-form pattern: 2025 and 2026 get their own ruleset IDs and effective windows, while formula bodies remain identical because casilla 00558 carries the statutory rate selected by the taxpayer.

Tax-rate split modeling: no enum or branch is required inside the current ruleset because the form prints the selected rate in casilla 00558. Worked examples cover general 25 percent, reduced-size transitional rates, new-entity/startup 15 percent, and microenterprise transitional first-band rates. The future full-form scope can introduce a strict Pydantic rate-regime model if the application starts deriving casilla 00558 from taxpayer attributes.

Depreciation-table modeling: deferred. The current extractor does not capture asset-level amortization lines or the accounting-to-tax adjustment pages. Full depreciation support needs a table representation over LIS art. 12 and RIS rules, plus asset-class inputs that do not exist in the current synthetic PDF surface.

Loss-carryforward modeling: deferred beyond the extracted `00547` input. LIS art. 26 requires multi-year BIN history and taxpayer state; verifying the already-printed compensation value is in scope, but deriving it is not.

L1 anchor decision: waiver for this issue. The public BOE model layout and AEAT instructions are suitable legal anchors, while taxpayer declaration PDFs are not safe to vendor without redaction/provenance work. L3 synthetic PDFs continue to verify extractor and CLI roundtrip behavior.
