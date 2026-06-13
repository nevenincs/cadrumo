---
step_id: S103
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P03.S103 — wizard status verb localization

## Outcome

Replaced the hardcoded English `verb` literal in the wizard tab-output path with
locale-resolved `verb_label` computed via `tr("wizard.commands.status.created")` /
`tr("wizard.commands.status.updated")` in `_command_body` inside
`build_wizard_command`.

The JSON payload key (`"status": verb`) retains the machine-readable English string.
Only the human-facing `typer.echo(f"status\t{verb_label}")` line is localized.

Locale keys added to all four locales (en, es, ca, hu) under `wizard.commands.status`.

## Files touched

- `src/aeat/application/wizard/_commands.py`
- `src/aeat/locales/en.yml`, `es.yml`, `ca.yml`, `hu.yml`

## Verification

`uv run --no-sync pytest src/aeat/application/wizard/test_commands.py -q`
→ 2 passed.

Commit: `fa0c58109` (wizard _commands verb_label) + `078eb3976` (locales parity sweep).
