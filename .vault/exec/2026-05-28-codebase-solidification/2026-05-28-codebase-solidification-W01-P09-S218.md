---
step_id: S218
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P09.S218 — persistence boundary roundtrip assertion test

## Outcome

Created `src/aeat/test_roundtrip_coverage.py` with two tests:
- `test_persistence_boundary_roundtrip_tests_exist`: every entry in
  `_BOUNDARY_ROUNDTRIP_INVENTORY` (26 boundaries, 26 test file paths) must
  exist on disk. Fails immediately when a roundtrip test is deleted without
  updating the inventory.
- `test_roundtrip_inventory_has_no_duplicate_paths`: no test path appears
  under two different boundary labels (copy-paste guard).

## Files touched

- `src/aeat/test_roundtrip_coverage.py` (new)

## Verification

`uv run --no-sync pytest src/aeat/test_roundtrip_coverage.py -q` — 2 passed.
