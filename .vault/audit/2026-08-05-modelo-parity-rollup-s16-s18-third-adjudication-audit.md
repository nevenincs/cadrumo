---
tags:
  - '#audit'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:427dfc58d93cfe0ad0bb294a1e03a6b253fae1f86d7e306087fe923431319a5a'
related:
  - "[[2026-08-05-modelo-parity-rollup-s16-0150-oracle-addendum-research]]"
  - "[[2026-08-05-modelo-parity-rollup-s18-1481-oracle-addendum-research]]"
  - "[[2026-08-05-modelo-parity-rollup-semantic-decision-boundary-audit]]"
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
---
# `modelo-parity-rollup` audit: `S16 S18 third SOL adjudication`

## Scope

Review the focused S16 `0150` rental-oracle addendum and S18 `1481` activity-oracle addendum after the Luna Max/XHigh evidence work. This audit records the third SOL decision and the allowed implementation boundary. It does not authorize production schema or source changes.

## Findings

### S16 / 0150 | high | persisted rental source is not calculation-ready

The Luna S16 worker correctly created no test artifact. The bundled 2025 worked example requires furniture amortization of `388.13` and nine-of-twelve period allocation of expenses and amortization, producing `2,562.91` deductible expenses and `2,958.38` reduction. Current persisted fincas models expose building amortization and unallocated expense records, but not the separate furniture or contract-period facts needed to represent the example honestly.

SOL decision: `0150` remains manual/open. The smallest next gate is a real persisted finca input flowing through the production source-readiness and aggregate path, with an independent expected-value oracle and an accepted mapping to the repeated `0150` filing rows.

### S17 / 0613 | high | 2025 producer contract remains ungrounded

The new addenda provide no new 2025 legal formula, complete input contract, or independent `0613` value. The 2024 producer cannot be cloned into 2025.

SOL decision: `0613` remains manual/open. The smallest next gate is a 2025-specific legal formula and complete child/month/net-expenditure input contract followed by an independent numeric oracle.

### S18 / 1481 | high | activity oracle does not prove M100 transfer

The new Luna test `src/cadrumo/domain/calculations/registry/tests/test_modelo_131_2025_activity_oracle.py` runs the real 2025 M131 engine for epigraphs `972.1` and `721.2` in all four quarters. It preserves separate activity keys and reproduces `22,473.79` and `8,987.09` annual-base values. It deliberately creates no aggregate and no M100 relation.

SOL decision: `1481` remains manual/open. The smallest next gate is a legally grounded 2025 mapping identifying source values, activity/period identity, annualization and aggregation semantics, plus an independent expected M100 `1481` value.

## Recommendations

Do not modify the 2025 `0150`, `0613`, or `1481` input kinds, formulas, bindings, relations, aggregate semantics, or source-readiness behavior until the row-specific gates are satisfied and SOL re-adjudicates the addenda. Keep all three plan steps open and report the independent oracle results as prerequisite evidence only.

## Consolidated decision

Neither addendum authorizes a production semantic change. The allowed production-file set is empty. Do not clone the 2024 M100–M131 contract or assume four quarterly values should be summed.

## Verification boundary

- S18 focused oracle: 1 test passed.
- S18 Ruff check and format check passed.
- S18 basedpyright reported 0 errors, warnings, or notes.
- Existing S17 source oracle remains 3 tests passed.
- No S16 artifact was claimed because its required persisted fields are absent.
- S16, S17, and S18 remain open in the plan; no execution record was created to falsely close them.
