---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W05.P024'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-root-help-shape-adr]]'
---



# `cli-workflow-redesign` `W05.P024`

Completed the real behavior verification phase for root help and discovery
behavior.

- Modified: `src/aeat/application/operator_surface/test_contract.py`
- Created: `src/aeat/entrypoints/cli/test_root_help_shape.py`

## Description

Added backend contract tests for help document ownership and active profile
landing report behavior. Added CLI behavior tests through Typer's runner that
exercise root help, config help, app help, and bare-root landing behavior
against the real workflow state repository. The tests isolate storage through
environment variables but do not stub the application services.

Closed plan rows: `W05.P024.S0139`, `W05.P024.S0140`,
`W05.P024.S0141`, `W05.P024.S0142`, `W05.P024.S0143`,
`W05.P024.S0144`.

## Tests

`uv run --no-sync pytest src/aeat/application/operator_surface/test_contract.py src/aeat/entrypoints/cli/test_root_help_shape.py -q`

`uv run --no-sync pytest src/aeat/application/operator_surface/test_contract.py src/aeat/application/test_apex_workflow_verification.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_apex_workflow_verification.py src/aeat/entrypoints/cli/test_root_help_shape.py src/aeat/entrypoints/cli/test_profile_output_language.py src/aeat/core/i18n/test_output_language.py -q`
