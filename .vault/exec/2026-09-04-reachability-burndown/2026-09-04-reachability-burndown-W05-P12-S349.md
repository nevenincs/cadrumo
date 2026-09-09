---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:51cdfdb172650a0013725cbf78120ecc807708a536649479f7f70bc55c4dafc9'
step_id: 'S349'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only CLI manager frontend helper and its source-policy and retired-symbol inventory test.

## Scope

- `manager frontend remnant`
- `wizard behavior tests`
- `live profile CLI`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/entrypoints/cli/config/_manager_frontend.py`
- `D` `src/cadrumo/entrypoints/cli/config/tests/test_manager_frontend_routing.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/wizard/tests/test_commands_helpers.py src/cadrumo/application/wizard/tests/test_flow_description_keys.py src/cadrumo/application/wizard/tests/test_wizard_validation_localization.py` -> `pass`
- `verify:` `uv run --no-sync aeat config profile --help` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
