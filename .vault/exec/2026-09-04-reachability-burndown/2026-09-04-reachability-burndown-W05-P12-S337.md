---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:6263f20a4af9fe62ad2ceaa4e0dcc688c47d06727f4c20032b349985d59f5d05'
step_id: 'S337'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Remove the duplicate source-policy engine from the CI command-spec authority test

## Scope

- `CI command graph test`
- `public API invariants`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `M` `dev/ci/tests/test_command_spec_authority_gate.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q dev/ci/tests/test_command_spec_authority_gate.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

Exact remeasurement reports the campaign's remaining live signal: 36 unreachable modules and 278 unused symbols.
