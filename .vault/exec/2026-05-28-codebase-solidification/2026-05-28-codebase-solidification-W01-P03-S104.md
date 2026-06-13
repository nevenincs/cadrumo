---
step_id: S104
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P03.S104 — wizard status verb localization tests

## Outcome

Created `src/aeat/application/wizard/test_commands.py` with two real-behavior tests:

- `test_wizard_create_status_verb_is_localized`: invokes wizard create via
  `build_wizard_command(SETUP_FLOW, mode="create")` through a real Typer app and
  `CliRunner`, asserts `status\t{tr("wizard.commands.status.created")}` in output.
- `test_wizard_edit_status_verb_is_localized`: seeds a profile, then runs wizard edit,
  asserts `status\t{tr("wizard.commands.status.updated")}` in output.

Expected values are derived from the locale authority via `tr()` at call time, not
hardcoded English literals.

## Files touched

- `src/aeat/application/wizard/test_commands.py` (new)

## Verification

`uv run --no-sync pytest src/aeat/application/wizard/test_commands.py -q`
→ 2 passed.

Commit: `2e0b00924`.
