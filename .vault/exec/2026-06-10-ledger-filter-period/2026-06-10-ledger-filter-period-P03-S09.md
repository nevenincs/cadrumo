---
tags:
  - '#exec'
  - '#ledger-filter-period'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S09'
related:
  - "[[2026-06-10-ledger-filter-period-plan]]"
---

# Run the full ledger-filter test suite and confirm zero failures after the six migrations

## Scope

- `src/aeat/application/aggregation/tests/`
- `src/aeat/entrypoints/cli/tests/`

## Description

- Run the period-filter owner surface: the three new modules (`test_period_boundary_authority.py`, `test_aggregation_period_for_modelo.py`, `test_period_continuity.py`) and the full `application/aggregation/tests/` unit suite.
- Run the four migrated CLI files plus `test_ledger_period_grammar.py` under `-m "unit or integration"`.
- Triage every residual failure against the period-filter feature surface per `full-tree-gate-must-distinguish-owner`.

## Outcome

Period-filter owner surface is GREEN:

- `application/aggregation/tests/` — 437 passed.
- The three new period modules — 143 passed.
- The migrated CLI period-filter call sites and `test_ledger_period_grammar.py` — pass.

Two residual failures remain in the broader CLI suite, both triaged to the sibling typed-core-`Period` refactor (W02.P08), NOT period-filter grammar:

- `test_ledger_persona_yearend_m100.py::test_no_annual_money_rollup_surface_exists` — asserts the `ledger status` JSON `period` equals the string `"2025"`; the status payload now serialises period as the structured `{'code': '0A', 'filing_year': 2025}` object (typed-`Period` projection change).
- `test_ledger_corpus_journeys.py::test_modification_refused_when_row_feeds_finalized_modelo` — passes `period="1T"` (str) to `derive_work_unit_id` / `WorkUnit`, which now require a typed `core.Period` (`ModeloValidationError: expected Period, got str`).

Neither failure is a period-boundary regression: both are stale test fixtures lagging the typed-`Period` domain contracts that landed in parallel. `test_ledger_corpus_journeys.py` additionally carried active peer WIP (ledger-amount-direction) at closure, so it was not re-touched (abort-on-WIP discipline).

## Notes

Step marked complete for the period-filter feature surface, which is at zero failures. The two residual failures are out-of-owner-surface sibling typed-`Period` reconciliations and are owned by the W02.P08 campaign; they are recorded here rather than absorbed, per `full-tree-gate-must-distinguish-owner` ("do not patch unrelated peer work just to green a closeout gate") and the brief's directive to avoid sibling ledger-hardening scope.
