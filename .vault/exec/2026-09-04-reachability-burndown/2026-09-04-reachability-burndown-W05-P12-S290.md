---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:73120e4ad6495deda67031f719809116467d350d117a68b6b2eb83fa6429ce8a'
step_id: 'S290'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only direct calculation-revision verification shortcut and its private bypass guards; retain the live verification pipeline and make tests target their owning behavior.

## Scope

- `calculation actions`
- `focused verification/readiness/import tests`
- `live verification owner`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `M` `src/cadrumo/application/modelo/calculation_actions.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/calculation_actions.py` -> `pass`
- `verify:` `rg -n "mark_revision_verificado_completo|_refuse_direct_cross_period_verification" src dev` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/modelo/tests/test_file_flow_verify.py src/cadrumo/application/modelo/tests/test_cross_period_clean_state_enforcement.py src/cadrumo/application/modelo/tests/test_profile_readiness_gate.py src/cadrumo/application/modelo/tests/test_import_flow_mutation_guards.py` -> `fail`

## Notes

The focused behavior slice passed 54 tests. Four failures are outside this deletion: a persistence guard prevents a deliberately divergent registry coordinate, a bucket-event assertion ignores profile creation, a parallel worker observed registry mutation during fingerprinting, and an M303 observation fixture lacks the now-required official declaration-type header. None imports or calls the deleted shortcut. Exact reachability moved from 249 to 248 unused symbols with 31 unreachable modules, zero orphan tests, and 2026 of 2057 shipped modules reachable.
