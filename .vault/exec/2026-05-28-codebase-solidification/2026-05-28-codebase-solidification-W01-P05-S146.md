---
step_id: S146
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P05.S146 — real-behavior test for fincas rounding

## Outcome

Added `src/aeat/domain/fincas/test_rounding.py` with 12 parametrized
`pytest.mark.unit` + `pytest.mark.domain_model` cases. Each case asserts an
expected `Decimal` output derived from Python's decimal specification and
IEEE 754-2008 ROUND_HALF_UP semantics. Covers: half-up boundary at 0.005 (rounds
up), 0.004 (rounds down), 0.014 / 0.015 boundary, exact cents unchanged, large
values with sub-cent fraction, negative values (ROUND_HALF_UP applied to absolute
value), and zero invariance. Every case additionally asserts the result has
exactly two decimal places via `as_tuple().exponent == -2`.

## Files touched

- `src/aeat/domain/fincas/test_rounding.py` (created)

## Collision check

File did not exist before creation — no peer WIP possible.

## Test outcome

12/12 passed: `uv run --no-sync pytest src/aeat/domain/fincas/test_rounding.py -xvs`
