---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P03.S05'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P03.S05`

The `reset-state` command refuses any mutating invocation lacking
`--yes` by raising `CliRefusedBoundaryError` with a localised refusal
message.

- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`

## Description

The refusal gate mirrors the existing `repair quarantine` pattern in
the same module: when `--yes` is absent the command raises
`CliRefusedBoundaryError(tr("cli.config.repair.reset_state_requires_yes"))`.
`--dry-run` deliberately skips the refusal gate so the operator can
inspect the envelope fingerprint without confirming; the gate fires
only when the operator asks for a real mutation without confirmation.
The boundary handler in `command_error_boundary` then routes the
refusal to stderr with the registered exit code, matching every
other `--yes`-gated CLI command.

## Tests

`test_reset_state_without_yes_or_dry_run_raises_refusal_and_keeps_row`
in `test_repair_reset_state.py` asserts a non-zero exit code plus
row survival.
