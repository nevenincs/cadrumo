---
tags:
  - '#exec'
  - '#core-authority'
step_id: S04
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W02.P02.S04 — CoreValidationError catch-order contract

## Status

CoreValidationError(CoreError, ValueError) was already correct — inherits from
CoreError. No production code change needed.

## Files touched

- `src/aeat/core/errors/test_core_error_root.py` — extended with S04 tests

## Verification gate

`pytest src/aeat/core/errors/test_core_error_root.py -x -q` — 5 passed.

## Commit

`f6a150f4b` — feat(errors): W02.P02.S04 CoreValidationError catch-order contract
