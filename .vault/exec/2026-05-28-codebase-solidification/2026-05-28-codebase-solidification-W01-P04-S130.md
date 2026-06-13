---
step_id: S130
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P04.S130 — Google Sheets boundary rationale assertion test

## Outcome

Created `src/aeat/adapters/outbound/google/test_calc_sheets_apply.py` with three
real-behavior tests:

- `test_calc_sheets_apply_source_exists` — guards the file exists before any assertion.
- `test_calc_sheets_apply_boundary_rationale_comment_present` — reads `_calc_sheets_apply.py`
  and asserts the `"irreducible"` marker is present, enforcing the third-party-rationale
  policy for Google Drive API boundary shapes.
- `test_calc_sheets_apply_boundary_anchor_present` — parametrised over the function
  anchor `"``_find_folder``"`, confirming the comment targets the specific boundary function.

These tests complement `src/aeat/adapters/test_boundary_rationale.py` (pi3/S136) which
already covers this file at a higher level; the new tests are local to the apply adapter
and express the anchor more precisely.

## Files touched

- `src/aeat/adapters/outbound/google/test_calc_sheets_apply.py` (created)

## Collision check

File did not exist before creation.

## Test outcome

42/42 pass including all three new tests.
