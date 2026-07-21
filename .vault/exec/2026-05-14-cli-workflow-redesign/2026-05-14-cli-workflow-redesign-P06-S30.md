---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-08'
step_id: 'S30'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

# Add negative tests proving Modelo 145 has no filing, deadline, live-read, portal, submit, receipt, or AEAT electronic tramite surface

## Scope

- `tests`

## Description

Extend Modelo 145 registry foundation tests with the full forbidden filing-like surface set named by the step.

Add CLI command-namespace negative tests proving the `m145` subgroup does not expose forbidden filing, deadline, live-read, portal, submit, receipt, or AEAT electronic tramite verbs.

Keep the assertions negative and behavior-free: the tests verify absence of forbidden surfaces without adding new command handlers, aliases, or registry conventions.

## Outcome

`src/aeat/domain/calculations/registry/tests/test_modelo_145_registry_foundation.py` now rejects the full forbidden surface vocabulary in Modelo 145 application links.

`src/aeat/entrypoints/cli/tests/test_m145_communication_cli.py` now parameterizes forbidden command surfaces and confirms Typer rejects each under `app modelo m145`.

Verification:

- `uv run --no-sync ruff format --check src\aeat\domain\calculations\registry\tests\test_modelo_145_registry_foundation.py src\aeat\entrypoints\cli\tests\test_m145_communication_cli.py`
- `uv run --no-sync ruff check src\aeat\domain\calculations\registry\tests\test_modelo_145_registry_foundation.py src\aeat\entrypoints\cli\tests\test_m145_communication_cli.py`
- `uv run --no-sync pytest src\aeat\domain\calculations\registry\tests\test_modelo_145_registry_foundation.py -q`
- `uv run --no-sync pytest src\aeat\entrypoints\cli\tests\test_m145_communication_cli.py -m integration -q`

## Notes

No blockers. No production behavior or registry data changed.
