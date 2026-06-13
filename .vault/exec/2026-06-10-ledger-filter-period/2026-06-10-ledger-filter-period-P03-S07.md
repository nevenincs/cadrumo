---
tags:
  - '#exec'
  - '#ledger-filter-period'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S07'
related:
  - "[[2026-06-10-ledger-filter-period-plan]]"
---

# Migrate test_ledger_persona_yearend_m100.py from bare 2025/2026 to 2025-0A/2026-0A

## Scope

- `src/aeat/entrypoints/cli/tests/test_ledger_persona_yearend_m100.py`

## Description

- Replace the bare-year period notation with the canonical annual AEAT token expressed as separate filter clauses: `--filter period=0A --filter year=2025` (and `2026`), and the `--period 0A --year 2025` command form.
- Align the quarter-iteration site (`test_all_four_quarters_reviewable`) to the year-always-separate grammar: `--filter period=1T --filter year=2025` rather than the combined `period=2025-1T` form, which the current grammar refuses with `ledger-period-year-pairing`.

## Outcome

The bulk migration landed in commit `c1c90df33`. The residual combined-token site in `test_all_four_quarters_reviewable` was closed in this session's commit `86a6102e7` (test(ledger-filter-period): align quarter-review filter to year-always-separate grammar (P03.S07)). Verified: the full file run reports the period-filter sites green; ruff clean.

## Notes

The combined `period=2025-1T` site survived the original P03 migration because the year-always-separate grammar (C6 reconcile, commit `c5cdf8fdf`) landed afterwards. One unrelated failure remains in this file (`test_no_annual_money_rollup_surface_exists`) — see P03.S09 notes — caused by the sibling typed-`Period` status-payload change, not period-filter grammar.
