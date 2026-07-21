---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S416'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---

# R10-HIGH converge monthly period boundaries on core Period

## Scope

- `retain only Modelo 202 instalment mapping in the helper`
- `add all-contiguous-token parity and Modelo 349 month-midpoint regressions.`
- `src/aeat/domain/period.py src/aeat/application/modelo/ src/aeat/domain/tests/`

## Description

- Replaced duplicated quarter, annual, and monthly boundary calculations with delegation to the canonical typed `Period` value.
- Preserved the explicit Modelo 202 `1P`–`3P` payment-month mapping because instalment codes intentionally have no contiguous `Period` span.
- Added canonical start-and-end parity coverage for every contiguous registry token: four quarters, annual, and all twelve monthly values.
- Added a real Modelo 349 March-20 intracommunity ledger regression that proves the monthly raw-row guard fails closed instead of silently excluding the transaction.
- Ran the focused 38-test period and Modelo 349 slice plus Ruff, then obtained independent code-review approval.

## Outcome

Monthly period end dates now agree with the canonical `Period` authority. Modelo calculation context, export fallback, taxonomy comparison, registry replay, and the Modelo 349 raw-ledger guard no longer use the incorrect first-of-month result.

## Notes

The first review found that direct parity covered only monthly tokens. The follow-up added quarterly and annual tokens; the re-review approved the complete contiguous-token surface.
