---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:b0bb463e03b70bb84c3a3ac54fe72bffc46d0c8c2998a3d4c42e9447bc005e9b'
step_id: 'S350'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unwired wizard registered-values and legal-zone projections and their module-status inventory tests.

## Scope

- `wizard projections and tests`
- `flow owner behavior`
- `locale rationale`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/application/wizard/_registered_values.py`
- `D` `src/cadrumo/application/wizard/legal_zone.py`
- `D` `src/cadrumo/application/wizard/tests/test_registered_values.py`
- `D` `src/cadrumo/application/wizard/tests/test_legal_zone.py`
- `D` `src/cadrumo/application/wizard/tests/test_public_definition_identity.py`
- `M` `dev/locales/tests/test_tr_constant_naming_convention.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/flows/tests/test_definition.py src/cadrumo/application/flows/tests/test_copy_assembly.py src/cadrumo/application/flows/tests/test_line_frontend.py src/cadrumo/application/wizard/tests/test_commands_helpers.py src/cadrumo/application/wizard/tests/test_flow_description_keys.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/locales/tests/test_tr_constant_naming_convention.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
