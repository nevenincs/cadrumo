---
step_id: S154
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-28-codebase-solidification-W01-P05-S153]]"
---

# codebase-solidification W01.P05.S154 — real-behavior tests for `coerce_decimal`

## Outcome

Created `src/aeat/core/decimal/test_coerce.py` with 36 parametrized
real-behavior tests covering all policy variants of the canonical
`coerce_decimal` helper.

## Coverage

- Valid inputs (Decimal, int, float, str, whitespace-padded str) — 12 cases
- Absent inputs (None, empty string) returning None — 2 cases
- Malformed inputs returning None — 5 cases
- Aggregation policy `default=Decimal("0")` — 7 cases
- Custom non-zero default — 5 cases
- Object identity: Decimal passthrough returns same object — 1 case
- Special Decimal tokens (Inf, -Inf, Infinity, NaN) — 4 cases

All 36 tests pass. No mocks, no skips, no xfail, no tautological assertions.

## Files

- `src/aeat/core/decimal/test_coerce.py` — created
