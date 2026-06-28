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

# exec phase4 task1 — tautology regression defense module

## What

New file `src/aeat/domain/formulas/_rulesets/test_mutator_tautology_regression.py`
with 4 tests:

- `test_aggregator_catches_uncovered_populated_node` — synthetic
  scenario where a fake EXPECTED_COUNTS row declares
  `mul_div_scalar=1` and `mul_div_scalar_deferred=0` (i.e. claiming
  full coverage for a node the per-class harness does not exercise).
  Asserts the new
  `test_deferred_count_matches_empirical_coverage_gap` invariant
  raises with the descriptive remediation hint.
- `test_aggregator_catches_inflated_deferred_count` — symmetric:
  `mul_div_scalar=0` with `mul_div_scalar_deferred=1` (over-claim).
  Asserts the invariant fails (it's an equality, not just a
  lower-bound).
- `test_aggregator_passes_when_deferred_matches_gap` — positive
  control: `mul_div_scalar=1` with `mul_div_scalar_deferred=1` (the
  one node is deferred). Asserts the invariant passes.
- `test_old_killed_equals_populated_pattern_is_unreachable` — AST
  guard. Walks `ast.parse(test_mutator_kill_rate.__source__)` for
  any single-target assignment of the literal name `populated` to
  the literal name `killed`. Fails if the prior tautology
  assignment reappears. AST-based detection ignores docstrings and
  comments so the guard only fires on actual code.

Module-level
`pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]`.

## Why

The structural defense for the issue-#457 fix. The
`test_deferred_count_matches_empirical_coverage_gap` invariant in
`test_mutator_kill_rate` would not have caught a future PR that
silently re-introduces `killed = populated` (because the literal
assignment is in the wrong file). The regression module's AST guard
+ synthetic-counter-example tests ensure the failure mode that
issue #457 fixed cannot return without breaking these tests.

## Verification

`uv run pytest src/aeat/domain/formulas/_rulesets/test_mutator_tautology_regression.py -q`
→ 4 passed.
