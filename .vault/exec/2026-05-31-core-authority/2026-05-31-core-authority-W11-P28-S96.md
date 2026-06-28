---
step_id: S96
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
---

# core-authority W11.P28.S96 step record

## Step

Implement Clause 9 asserting no two production modules outside the protect list declare an `UPPER_SNAKE_CASE` constant with the same name and same literal value, with anti-tautology proof.

## Status

COMPLETE

## Implementation

Added `find_same_name_constant_multi_declarations()` to `src/aeat/diagnostics/_identity_placement.py`.
The detector walks every production module (excluding test files), collects module-level
`UPPER_SNAKE_CASE` name assignments whose value is a simple literal (int, float, str, bytes,
or unary-negated number), groups by `(name, repr(value))`, and reports all modules sharing
the same pair across different module paths. Protect-list modules excluded.

Added to test file:
- `test_no_same_name_constant_multi_declarations()` — zero-violation assertion against the
  current production tree. Passes.
- `test_same_name_constant_detector_flags_synthetic_violation()` — anti-tautology proof.

## Test result

`pytest src/aeat/diagnostics/test_identity_primitive_placement.py::test_no_same_name_constant_multi_declarations` — PASSED (0 violations on current tree).

All 17 tests in the file pass.

## Commit

`8a08cac3f` — diagnostics(W11.P28): extend enforcement test to 10 clauses per Rule 11

## Files touched

- `src/aeat/diagnostics/_identity_placement.py`
- `src/aeat/diagnostics/test_identity_primitive_placement.py`
