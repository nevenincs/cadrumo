---
tags:
  - '#exec'
  - '#ledger-filter-period'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S12'
related:
  - "[[2026-06-10-ledger-filter-period-plan]]"
---

# Update test_no_annual_money_rollup_surface_exists to assert the ledger status period payload as the typed-Period object the W02.P08 refactor now serialises

## Scope

- `src/aeat/entrypoints/cli/tests/test_ledger_persona_yearend_m100.py`

## Description

- Replace `assert result["period"] == "2025"` with `assert result["period"] == {"filing_year": 2025, "code": "0A"}`, matching the structured period the `ledger status` JSON payload now emits after the typed-core-`Period` refactor (W02.P08).
- The invocation already used the canonical `--period 0A --year 2025` form; only the response-shape assertion lagged.

## Outcome

Landed in commit `076f4ffe7` (test(ledger-filter-period): assert typed-Period status payload in yearend persona (P05.S12)). Verified green: the three-test reconciliation run (`test_no_annual_money_rollup_surface_exists`, `test_modification_refused_when_row_feeds_finalized_modelo`, `test_all_four_quarters_reviewable`) reports 3 passed.

## Notes

Absorbed into the ledger-filter-period plan as P05 at operator request, treating the sibling typed-`Period` failures as in scope. Worked concurrently with the typed-`Period` campaign that owns the production-side contract; this is a single-purpose test-assertion update to the landed shape, not a production change.
