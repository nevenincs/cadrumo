---
tags:
  - '#exec'
  - '#mutation-harness-fix'
date: '2026-04-29'
modified: '2026-04-29'
related:
  - '[[2026-04-29-mutation-harness-fix-plan]]'
  - '[[2026-04-29-mutation-harness-fix-adr]]'
---

# exec phase2 task2 — refactor aggregate kill-rate test

## What

`src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py`:

- Replaced the `killed = populated` tautology in
  `test_aggregate_kill_rate_floor_is_satisfied` with empirical
  coverage computed via `_empirical_scalar_coverage`,
  `_empirical_percent_coverage`, and `_empirical_sub_op_coverage`.
- Added `_POPULATED_KEYS`, `_DEFERRED_KEYS`, `_NUMERIC_BRACKETS_SYNTHETIC`
  module constants.
- Added two new tests:
  - `test_expected_counts_rows_carry_required_columns` — asserts
    every `EXPECTED_COUNTS` row carries the required populated and
    deferred keys.
  - `test_deferred_count_matches_empirical_coverage_gap` — the
    issue-#457 regression-defense invariant: per (ruleset, mutator
    class), `populated - empirical == declared_deferred`.
  - `test_aggregator_killed_equals_populated_under_test` — guards
    against per-class harness drift (over-coverage vs declared).
- Updated `test_per_ruleset_node_counts_match_expected` to compare
  only the populated keys (deferred keys are not produced by
  `_count_per_ruleset`).
- Updated `EXPECTED_COUNTS`: every row gains
  `sub_op_deferred` and `mul_div_scalar_deferred` columns matching
  the empirical coverage gap (per ADR D2).
- Updated `build_catalogue_markdown()` and the catalogue tests to
  surface the deferred columns.

## Why

The prior aggregator hardcoded `killed = populated`, making the 90 %
kill-rate floor vacuous on any node not enumerated by the per-class
harnesses. The PR #448 M100 megaproject exposed the gap (60 mul/div
scalar leaves and 213 sub_op nodes silently absent from the
per-class harness). The empirical computation + deferred catalogue
+ gap-equality invariant is the issue-#457 fix.

## Verification

`uv run pytest src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py -q`
→ 38 passed (was 35 pre-#457). The kill-rate floor is now computed
on the claimed-covered surface (16 of 16 covered = 100 %).
