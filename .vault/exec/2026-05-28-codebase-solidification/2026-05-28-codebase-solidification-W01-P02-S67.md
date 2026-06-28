---
step_id: S67
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P02.S67 — wizard emit_progress via structured logger

## Outcome

Replaced `sys.stdout.write(f"{text}\n"); sys.stdout.flush()` in
`QuestionaryPrompter.emit_progress` at `src/aeat/application/wizard/_prompter.py`
with `_log.info("wizard.progress text=%r", text)` using the module-level
`_log = get_logger(__name__)` instance already present in the file. Updated the
docstring to reflect the structured-log routing. `import sys` is retained because
`sys.stdin.isatty()` is still used in `_ensure_interactive_environment`.

## Files touched

- `src/aeat/application/wizard/_prompter.py`

## Verification

77 tests pass. Commit: 2f51c3e0d. `vault plan step check S67` applied.
