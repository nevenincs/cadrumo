---
tags:
  - '#exec'
  - '#arch-remediation-gates-ratchet'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:e533b3240c84d26b5a7093ac370ba91c5f4817ea68e75db603280a740758b253'
step_id: 'S08'
related:
  - '[[2026-07-02-arch-remediation-gates-ratchet-plan]]'
---

# Confirm lint-imports with pinned edges

## Scope

- `.importlinter`

## Description

- Ran `uv run --no-sync lint-imports` after removing the blanket wildcard and after adding the exact pins required by the repaired ledger.

## Outcome

Import Linter passes: 4 contracts kept, 0 broken.

## Notes

The lint run analyzed 2962 files and 14284 dependencies after the test file was added.
