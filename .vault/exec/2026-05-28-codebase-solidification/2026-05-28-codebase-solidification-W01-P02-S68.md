---
step_id: S68
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P02.S68 — wizard prompter log routing tests

## Outcome

Extended `src/aeat/application/wizard/test_prompter.py` with two real-behavior
tests for `QuestionaryPrompter.emit_progress` after the S67 change:

- `test_emit_progress_routes_through_logger_not_stdout` — asserts
  `capsys.readouterr()` returns empty strings and a `wizard.progress` log
  record is captured at INFO level.
- `test_emit_progress_log_record_carries_text` — asserts the captured record
  set is non-empty (the event key is present for any progress text).

## Files touched

- `src/aeat/application/wizard/test_prompter.py`

## Verification

77 tests pass. Commit: 2f51c3e0d. `vault plan step check S68` applied.
