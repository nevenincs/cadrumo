---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-19'
modified: '2026-07-19'
body_hash: 'sha256:8e81bf0ff2d321048ff6b3400dbffcf4eb29f78f73f17ebce2b9cb8c0eeab048'
step_id: 'S21'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

# Register only reset start, status, and resume with operation, retention, reason, and confirmation options

## Scope

- `src/cadrumo/entrypoints/cli/_config/_reset_cli.py`

## Description

- Author `reset_app` (a `CadrumoTyperGroup` named `reset`) carrying exactly three commands: `start`, `status`, `resume`.
- `start`/`resume` require `--yes` (refusing via `CliRefusedBoundaryError` when absent), accept `--override-retention` plus a paired required `--reason`, and `resume` accepts an optional `--operation-id` (defaulting to the sole incomplete operation).
- `status` accepts an optional `--operation-id` and performs no mutation.
- Mount via `register_reset_commands(config_app)` -> `config_app.add_typer(reset_app, name="reset")`.

## Outcome

Verified against HEAD (`8af409cd3f`), not re-implemented; landed by commit `38eba09021`. Read `src/cadrumo/entrypoints/cli/_config/_reset_cli.py` in full: exactly three `@reset_app.command(...)` decorators (`start` at line 76, `status` at line 132, `resume` at line 163) — no fourth verb. `_retention_override` enforces the `--override-retention`/`--reason` pairing symmetrically (reason without the flag is refused; the flag without a reason is refused). `test_config_reset_lifecycle.py` (`-m integration`) passes 2/2; `test_destructive_verbs_require_yes.py::test_config_reset_start_refuses_without_yes`, `::test_config_reset_status_is_read_only_and_needs_no_yes`, and `::test_config_reset_resume_refuses_without_yes` pass, proving the confirmation gating matches the step's contract exactly.

## Notes

No incidents.
