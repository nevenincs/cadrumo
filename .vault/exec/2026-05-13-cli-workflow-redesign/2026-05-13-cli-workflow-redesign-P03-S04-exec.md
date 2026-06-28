---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P03.S04'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P03.S04`

Added the `aeat config repair reset-state` Typer command with
`--dry-run / --no-dry-run` (default false) and the mandatory `--yes`
flag, both rendered through `_emit` for json + text formats.

- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`
- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/es.yml`
- Modified: `src/aeat/locales/ca.yml`
- Modified: `src/aeat/locales/hu.yml`

## Description

The new command lives under `repair_app` inline in `_config/__init__.py`
(the plan named `_config/repair.py` but no standalone module exists
in this worktree; P01 confirmed the inline shape). The command:

- `--dry-run` (a `--dry-run/--no-dry-run` boolean Typer flag with
  `False` default): computes the fingerprint via
  `fingerprint_workflow_state()` and emits the dry-run payload
  without touching the row.
- `--yes`: required for the mutating run; in its absence (and absent
  `--dry-run`) the command raises `CliRefusedBoundaryError` (see
  P03.S05).
- When `--yes` is set, the command calls `reset_workflow_state()` and
  emits the post-mutation fingerprint payload.

Both branches emit through `_emit(ctx, payload, lines)` so the same
command honours `--format json|text`. The JSON payload carries
`dry_run` plus the fingerprint dump; the text payload renders the
fingerprint fields one per line. Translation keys
`cli.config.repair.reset_state_help`,
`cli.config.repair.reset_state_yes_help`,
`cli.config.repair.reset_state_dry_run_help`, and
`cli.config.repair.reset_state_requires_yes` were added to all four
locale catalogues so the help surface contains no raw translation
keys.

## Tests

Covered by `src/aeat/entrypoints/cli/_config/test_repair_reset_state.py`
(see P03.S06).
