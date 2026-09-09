---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:b72203cfce7eca92e42badf859ff96ef00cd239bac9f43cd72c7b989f713bb0a'
step_id: 'S295'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the hand-maintained identifier-namespace adjudication gate and the two unreachable profile snapshot DTOs it classified; retain the canonical UserProfileSnapshot domain owner and real profile service behavior.

## Scope

- `identifier namespace enrollment census`
- `user-profile command DTOs`
- `focused profile tests`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `M` `src/cadrumo/application/user_profile/commands.py`
- `D` `dev/identity/tests/test_identifier_namespace_enrollment_gate.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `rg -n <deleted DTO and adjudication-list names> src dev` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/user_profile/commands.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/user_profile/tests/test_services.py` -> `fail`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`

## Notes

The focused service suite passed 20 tests; one peer-owned failure observed the bundled registry changing during cache fingerprinting. Exact reachability moved from 244 to 242 unused symbols with 31 unreachable modules and zero orphan tests.
