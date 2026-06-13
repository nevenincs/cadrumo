---
step_id: S216
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P09.S216 — module coverage inventory assertion test

## Outcome

Created `src/aeat/test_coverage_inventory.py` with two tests:
- `test_new_production_modules_have_test_coverage`: fails if any production module
  outside `COVERAGE_GAPS` lacks a paired `test_*.py` in its directory.
- `test_coverage_gaps_declared_set_matches_reality`: fails if any `COVERAGE_GAPS`
  entry is stale (module deleted or now has a test).

`COVERAGE_GAPS` contains 71 entries (the S215 enumeration output). The gate is
forward-looking: new modules added without tests will fail CI immediately.

## Files touched

- `src/aeat/test_coverage_inventory.py` (new)

## Verification

`uv run --no-sync pytest src/aeat/test_coverage_inventory.py -q` — 2 passed.
