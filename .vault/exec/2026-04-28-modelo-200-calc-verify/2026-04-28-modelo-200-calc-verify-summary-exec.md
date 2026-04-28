---
tags:
  - '#exec'
  - '#modelo-200-calc-verify'
date: '2026-04-28'
related:
  - "[[2026-04-28-modelo-200-calc-verify-plan]]"
  - "[[2026-04-28-modelo-200-calc-verify-reference]]"
---

# `modelo-200-calc-verify` execution summary

## Changes

- Refactored `modelo_200_2024` to share casilla/formula builders across annual clones.
- Added `modelo_200.2025` and `modelo_200.2026`, each registered with a separate annual effective window.
- Added year-specific worked-example tests and rate-split examples for general, reduced-size, startup/new-entity, and microenterprise rates.
- Updated registry/listing/smoke tests and M200 mutation-harness enumerations.
- Updated the M200 CLI import workflow from `UNVERIFIABLE` to `VERIFIED`, with a tampered-discrepancy case.
- Added the rule-delta manifest and flipped M200 coverage documentation.

## Casilla Inventory

All three annual rulesets expose the same 16-casilla page-14 surface: 13 user-supplied casillas and 3 computed casillas. Computed casillas are 00562, 00611, and 00621.

## BOE Sources

- BOE-A-2014-12328, Ley 27/2014 LIS arts. 26, 29, 30, 30 bis, 39, and 125.
- BOE-A-2015-7771, RD 634/2015 RIS.
- BOE-A-2025-12818, Orden HAC/657/2025 for the 2024 layout.

The 2025 and 2026 annual Modelo 200 orders were not used because the relevant annual orders were not available on BOE as of 2026-04-28.

## Scope Decisions

- Tax-rate split: verified through printed casilla 00558; no enum branch added. Worked examples use the LIS transitional rates for 2025 and 2026.
- Depreciation tables: deferred until asset-level M200 extraction exists.
- Loss carryforward derivation: deferred because LIS art. 26 requires multi-year state; 00547 remains an input.
- Pillar 2/minimum tax and large-group minimum tax: deferred outside the page-14 MVP.
- Foral regimes and Canarias ZEC/RIC: deferred to territorial/special-regime work.
- L1 anchor: waiver; BOE sources plus L3 synthetic PDFs are used.

## Citation Audit

`uv run aeat audit rulesets citations`:

- `modelo_200.2024`: computed=3, with_citation=3, coverage=100.00%.
- `modelo_200.2025`: computed=3, with_citation=3, coverage=100.00%.
- `modelo_200.2026`: computed=3, with_citation=3, coverage=100.00%.
- Aggregate: computed=133, with_citation=133, coverage=100.00%.

## Mutation Status

The mutation inventory now includes each M200 annual ruleset:

| Ruleset | sub_op | compound percent skipped | scalar leaves |
| :--- | ---: | ---: | ---: |
| modelo_200.2024 | 5 | 1 | 1 |
| modelo_200.2025 | 5 | 1 | 1 |
| modelo_200.2026 | 5 | 1 | 1 |

Focused mutation tests passed for scalar mutation, operand-swap mutation, kill-rate aggregation, exhaustiveness, and zero-boundary coverage.

## Verification

Passed:

- `uv run pytest src/aeat/formulas/_rulesets/test_modelo_200_2024.py src/aeat/formulas/_rulesets/test_modelo_200_2025.py src/aeat/formulas/_rulesets/test_modelo_200_2026.py src/aeat/formulas/test_registry.py src/aeat/formulas/test_cli.py src/aeat/formulas/test_smoke.py tests/integration/test_kent_workflows.py::TestKentImportsModelo200Declaracion -q`
- `uv run pytest src/aeat/formulas/_rulesets/test_scalar_mutation.py src/aeat/formulas/_rulesets/test_operand_swap_mutation.py src/aeat/formulas/_rulesets/test_mutator_kill_rate.py src/aeat/formulas/_rulesets/test_mutator_exhaustiveness.py src/aeat/formulas/_rulesets/test_zero_boundary_coverage.py -q`
- `uv run aeat audit rulesets citations`
