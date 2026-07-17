---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S31'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

# Add negative tests proving Modelo 145 has no shims, stubs, fake support, deprecated spellings, or compatibility aliases

## Scope

- `tests`

## Description

Add CLI negative tests rejecting deprecated or compatibility-style aliases for Modelo 145 communication commands.

Add a backend-boundary source scan proving Modelo 145 production and registry files do not contain shim, stub, fake-support, deprecated-spelling, or compatibility-alias language.

Keep the anti-shim checks scoped to Modelo 145 production files and registry fragments so unrelated legitimate test prose does not create false positives.

## Outcome

`src/aeat/entrypoints/cli/tests/test_m145_communication_cli.py` now rejects common alias spellings such as `complete`, `deliver`, `mark-completed`, and `mark-delivered` under the `m145` command group.

`src/aeat/entrypoints/cli/tests/test_backend_boundary.py` now scans the M145 CLI modules, application service modules, and Modelo 145 registry source fragments for shim/stub/fake/deprecated/compatibility tokens.

Verification:

- `uv run --no-sync ruff format --check src\aeat\entrypoints\cli\tests\test_m145_communication_cli.py src\aeat\entrypoints\cli\tests\test_backend_boundary.py`
- `uv run --no-sync ruff check src\aeat\entrypoints\cli\tests\test_m145_communication_cli.py src\aeat\entrypoints\cli\tests\test_backend_boundary.py`
- `uv run --no-sync pytest src\aeat\entrypoints\cli\tests\test_m145_communication_cli.py -m integration -q`
- `uv run --no-sync pytest src\aeat\entrypoints\cli\tests\test_backend_boundary.py::test_modelo_145_shims_stubs_and_compatibility_aliases_stay_absent -m integration -q`

## Notes

No blockers. No production behavior changed.
