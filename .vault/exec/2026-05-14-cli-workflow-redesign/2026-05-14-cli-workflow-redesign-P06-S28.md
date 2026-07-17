---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S28'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

# Add real service tests for create, validate, export, delivered-to-payer, and locally completed behavior

## Scope

- `tests/application/modelo`

## Description

Add a real application-service flow test for Modelo 145 communication records.

Exercise create, validate, export, delivered-to-payer, and locally completed operations through the persisted bucket-local service runtime.

Verify the composed flow keeps the record in the expected lifecycle states and produces the registry-backed export payload without fake services or test-only shims.

## Outcome

`src/aeat/application/modelo/tests/test_m145_communication_service_flow.py` now covers the end-to-end backend service sequence using `isolated_runtime_profile` and application-facade imports.

Verification:

- `uv run --no-sync ruff format --check src\aeat\application\modelo\tests\test_m145_communication_service_flow.py`
- `uv run --no-sync ruff check src\aeat\application\modelo\tests\test_m145_communication_service_flow.py`
- `uv run --no-sync pytest src\aeat\application\modelo\tests\test_m145_communication_service_flow.py -q`
- `uv run --no-sync pytest src\aeat\application\modelo\tests\test_m145_communication_create.py src\aeat\application\modelo\tests\test_m145_communication_validate.py src\aeat\application\modelo\tests\test_m145_communication_export.py src\aeat\application\modelo\tests\test_m145_communication_transitions.py src\aeat\application\modelo\tests\test_m145_communication_service_flow.py -q`

## Notes

No blockers. No skipped gates. No fake, stub, monkeypatched, or compatibility test support was introduced.
