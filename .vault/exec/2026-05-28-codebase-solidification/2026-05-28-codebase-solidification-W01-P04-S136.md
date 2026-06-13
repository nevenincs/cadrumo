---
step_id: S136
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P04.S136 — boundary rationale assertion test

## Outcome

Created `src/aeat/adapters/test_boundary_rationale.py` with 3 parametrised
real-behavior tests (one per annotated adapter file):

- `outbound/google/_calc_sheets_apply.py` — asserts the `"irreducible"` marker
  substring is present in the file source.
- `outbound/storage/_google_drive.py` — same assertion.
- `outbound/aeat/browser/session.py` — same assertion.

The `"irreducible"` substring is embedded in every boundary rationale comment
added for the Google / Playwright `dict[str, Any]` boundaries.  If any comment
disappears during a refactor the test fails loudly.  Anti-tautological:
deleting the comment from any file causes the test to fail immediately.

No mocks, no skips, no xfail.  Mark: `unit` + `domain_outbound`.

## Files touched

- `src/aeat/adapters/test_boundary_rationale.py` (created, 3 tests)

## Test outcome

3 tests passed.
