---
step_id: S135
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P04.S135 — adapter dict[str, Any] boundary rationale audit

## Outcome

Audited all `-> dict[str, Any]` return signatures under `src/aeat/adapters/`.

Sites found and rationale-comment status:

- `_calc_sheets_apply.py:118` (`_find_folder`) — rationale present (pre-existing)
- `_calc_sheets_apply.py:166` (`_create_folder`) — rationale MISSING; added
- `_calc_sheets_apply.py:197` (`_find_spreadsheet`) — rationale MISSING; added
- `_calc_sheets_apply.py:235` (`_create_spreadsheet`) — rationale MISSING; added
- `_calc_sheets_apply.py:491` (`_condition_for_constraint`) — rationale MISSING; added
- `_google_drive.py:322` (`_find_file`) — docstring present but no `dict[str, Any]`
  rationale; added inline sentence in docstring
- `session.py:184` (`_build_context_kwargs`) — rationale present (pre-existing)

All newly annotated functions reference the detailed rationale on `_find_folder`
or explain the third-party API boundary inline.

No unannotated cases remain.  Wave 2 follow-up: consider whether the Google
adapter functions could use typed TypedDict stubs to narrow the boundary further,
reducing reliance on prose-only documentation.

## Files touched

- `src/aeat/adapters/outbound/google/_calc_sheets_apply.py` (4 rationale comments added)
- `src/aeat/adapters/outbound/storage/_google_drive.py` (1 rationale added to docstring)

## Collision check

Clean — `git diff` before first edit returned empty on target files.
