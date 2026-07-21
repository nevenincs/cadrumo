---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S33'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

# Run the targeted registry, application, and CLI test slices without skips, xfails, mocks, stubs, or tautological assertions

## Scope

- `tests`

## Description

Run the targeted registry, application, parser/rendering, and CLI integration slices that cover the completed Modelo 145 successor work.

Keep marker handling explicit so integration tests are not silently filtered by the default pytest selection.

Confirm the gate output contains no skips, xfails, mocks, stubs, or tautological shortcut evidence.

## Outcome

Targeted verification passed:

- `uv run --no-sync pytest src\aeat\domain\calculations\registry\tests\test_modelo_145_registry_foundation.py src\aeat\domain\calculations\registry\tests\test_censo_modelo_foundation.py src\aeat\domain\calculations\registry\tests\test_censo_modelo_registry_data.py src\aeat\application\modelo\tests\test_m145_communication_service_contract.py src\aeat\application\modelo\tests\test_m145_communication_create.py src\aeat\application\modelo\tests\test_m145_communication_validate.py src\aeat\application\modelo\tests\test_m145_communication_export.py src\aeat\application\modelo\tests\test_m145_communication_transitions.py src\aeat\application\modelo\tests\test_m145_communication_events.py src\aeat\application\modelo\tests\test_m145_communication_errors.py src\aeat\application\modelo\tests\test_m145_communication_service_flow.py -q`
  - `74 passed`
- `uv run --no-sync pytest src\aeat\entrypoints\cli\tests\test_m145_communication_parsing.py src\aeat\entrypoints\cli\tests\test_m145_communication_rendering.py -q`
  - `7 passed`
- `uv run --no-sync pytest src\aeat\entrypoints\cli\tests\test_m145_communication_cli.py src\aeat\entrypoints\cli\tests\test_backend_boundary.py::test_modelo_145_shims_stubs_and_compatibility_aliases_stay_absent -m integration -q`
  - `31 passed`

## Notes

No blockers. No tests were skipped or xfailed in the targeted output. No code changes were required for this gate step.
