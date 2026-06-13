---
step_id: S48
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S48 — ClassificationRuleError real-behavior tests

## Outcome

Created `src/aeat/domain/transactions/test_classification_rule.py` with five
real-behavior tests: registry membership, `build_error_envelope` round-trip,
invalid-regex raises (ValidationError with ClassificationRuleError as ctx error),
valid-regex constructs successfully, and ValueError inheritance check. No mocks,
no skips, no xfail.

## Files touched

- `src/aeat/domain/transactions/test_classification_rule.py` (new)

## Verification

`uv run --no-sync pytest src/aeat/domain/transactions/test_classification_rule.py -xvs` — 5 passed.
