---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W06.P029'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr]]'
---

# `cli-workflow-redesign` `W06.P029`

Completed the real behavior verification phase for central output rendering.

- Created: `src/aeat/core/test_output_rendering.py`
- Modified: `src/aeat/entrypoints/cli/test_registry_cli.py`

## Description

Added core service tests for text rendering, JSON rendering, project type
normalization, and registered rendering errors. Updated registry CLI tests to
exercise root `--format json` through real Typer commands and added a negative
test proving command-local `--json` no longer reaches retained registry
commands.

Closed plan rows: `W06.P029.S0169`, `W06.P029.S0170`,
`W06.P029.S0171`, `W06.P029.S0172`, `W06.P029.S0173`,
`W06.P029.S0174`.

## Tests

`uv run --no-sync pytest src/aeat/core/test_output_rendering.py src/aeat/entrypoints/cli/test_registry_cli.py src/aeat/entrypoints/cli/test_root_help_shape.py -q`

`uv run --no-sync pytest src/aeat/core/test_output_rendering.py src/aeat/application/operator_surface/test_contract.py src/aeat/application/overview/test_calendar.py src/aeat/application/test_apex_workflow_verification.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_apex_workflow_verification.py src/aeat/entrypoints/cli/test_root_help_shape.py src/aeat/entrypoints/cli/test_profile_output_language.py src/aeat/entrypoints/cli/test_registry_cli.py src/aeat/core/i18n/test_output_language.py -q`
