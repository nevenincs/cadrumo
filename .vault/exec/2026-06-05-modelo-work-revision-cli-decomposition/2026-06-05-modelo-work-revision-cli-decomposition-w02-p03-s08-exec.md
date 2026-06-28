---
tags: ['#exec', '#modelo-work-revision-cli-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S08'
related:
  - '[[2026-06-05-modelo-work-revision-cli-decomposition-plan]]'
---

# W02.P03.S08 Execution

Verified that workflow gate and command-specific revision defaults remain application-owned.

Grounding:
- `src/aeat/entrypoints/cli/_modelo_work_verification_cli.py` calls `_resolve_revision_for_cli(... default_for="verify")` and `_resolve_revision_for_cli(... default_for="file")`.
- `_resolve_revision_for_cli` delegates to the public application facade `resolve_modelo_revision_for_operator_target`.
- `resolve_modelo_revision_for_operator_target` dispatches `default_for="verify"` to `resolve_verifiable_modelo_calculation_revision_address`.
- `resolve_modelo_revision_for_operator_target` dispatches `default_for="file"` to `resolve_fileable_modelo_calculation_revision_address`.
- Workflow gate refusal remains in application actions; the CLI does not convert workflow gate refusals into bad CLI arguments.

Passed:
- `uv run --no-sync pytest src/aeat/application/modelo/test_selectors.py::test_current_command_specific_revision_selectors_enforce_state src/aeat/application/modelo/test_selectors.py::test_addressed_revision_policy_resolvers_enforce_command_specific_state src/aeat/application/modelo/test_work_addressing.py::test_revision_pick_defaults_are_command_specific_under_one_work_unit -q`
