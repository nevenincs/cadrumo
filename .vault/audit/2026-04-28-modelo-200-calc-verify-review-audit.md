---
tags:
  - '#audit'
  - '#modelo-200-calc-verify'
date: '2026-04-28'
modified: '2026-04-28'
related:
  - "[[2026-04-28-modelo-200-calc-verify-plan]]"
  - "[[2026-04-28-modelo-200-calc-verify-adr]]"
  - "[[2026-04-28-modelo-200-calc-verify-research]]"
---

# `modelo-200-calc-verify` code review

## Scope

Reviewed all changed files for issue 324: M200 rulesets, registry exports, ruleset tests, mutation tests, integration workflow tests, coverage docs, and vault artifacts.

## Findings

M200-001 | HIGH | 2024/2025 rate examples use rates from the wrong legal window
`test_modelo_200_2024` labels a 17 percent microenterprise first-band case as a 2024 worked example, and `test_modelo_200_2025` labels 20 percent as SME and 17 percent as the 2025 microenterprise first band. The BOE consolidated LIS text updated through 2026-03-21 makes the steady-state article 29 scale 17/20, but the transitional provision applies 21/22 for microenterprises and 24 for reduced-size entities for periods starting in 2025, and 19/21 plus 23 for periods starting in 2026. The issue scope explicitly requires external legal anchoring and per-year registration windows, so the examples and vault reference/research text should not claim those rates for 2024/2025.

Resolution: fixed in the implementation after review. The 2024 worked example now uses the 23 percent reduced microenterprise rate. The 2025 examples now use 24 percent for reduced-size entities and 21 percent for the first microenterprise band. The 2026 examples use 23 percent for reduced-size entities and 19 percent for the first microenterprise band. The research, rule-delta manifest, and execution summary now cite LIS transitional provision 44 for 2025/2026 rates.

No source-code arithmetic blocking findings recorded in the host review pass.

## Safety Invariants

- Cent-exact correctness: covered by per-year M200 worked examples for 00562, 00611, and 00621.
- External anchoring: expected values cite LIS arts. 29 and 30 through test docstrings and vault source inventory.
- Per-annum coverage: 2024, 2025, and 2026 are registered with non-overlapping annual windows.
- Citation enforcement: `aeat audit rulesets citations` reports 100 percent coverage on all M200 computed casillas.
- Mutation coverage: scalar, operand-swap, kill-rate, exhaustiveness, and zero-boundary focused tests passed.
- PDF roundtrip: M200 v2025 synthetic PDF import now verifies clean filings and classifies tampered 00621.
- Integration: `TestKentImportsModelo200Declaracion` retains complete English, complete Spanish, partial extraction, and discrepancy cases.
- L1 anchor: waiver documented in the rule-delta reference.

## Residual Risk

The annual orders for fiscal years 2025 and 2026 are not available on BOE as of 2026-04-28. The rulesets intentionally cite LIS/RIS for computation and avoid claiming future annual-order layout authority.
