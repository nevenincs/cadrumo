---
step_id: S78
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P03.S78 — draft_id_not_found test

## Outcome

Created `src/aeat/entrypoints/cli/test_common.py` with three real-behavior
tests covering the S77 change:

- `test_draft_by_id_raises_bad_parameter_for_unknown_id`: asserts
  `typer.BadParameter` is raised for an unknown draft ID under a real
  active-profile runtime.
- `test_draft_by_id_error_message_matches_locale_catalogue`: asserts the
  raised message exactly matches `tr("cli.common.errors.draft_id_not_found",
  draft_id=...)` and the old hard-coded f-string form is absent.
- `test_draft_by_id_error_message_contains_draft_id_interpolation`: asserts
  the actual `draft_id` value is present in the rendered message.

All tests use `isolated_cli_runtime_profile` for a real backend; no mocks.

## Files touched

- `src/aeat/entrypoints/cli/test_common.py` (created)

## Verification

`pytest src/aeat/entrypoints/cli/test_common.py -xvs` — 6 passed (includes S80
tests). `vault plan step check S78` applied.
