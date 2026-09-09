---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:31074e59fc7c9891f0a88c86ffa63b2430429890d9d92311f8349f2f907fe725'
step_id: 'S231'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unreachable review-kind reservation metastate: remove the test-only reserved-token map and accessor, dedicated ReviewKindReservedError, central error registration, and self-only registry/operator probes; retain the live source-kind selector and its generic fail-closed unknown-token refusal.

## Scope

- `Review queue enums/errors/operator tests`
- `central error registry and CLI registry contract`
- `accepted reachability authority`
- `exact symbol signal`
- `focused gates`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `src/cadrumo/application/review/enums.py`
- `M` `src/cadrumo/application/review/errors.py`
- `M` `src/cadrumo/application/review/tests/test_operator.py`
- `M` `src/cadrumo/core/errors/registry/_application_part1.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_error_registry_contract.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/review/enums.py src/cadrumo/application/review/errors.py src/cadrumo/application/review/tests/test_operator.py src/cadrumo/entrypoints/cli/tests/test_error_registry_contract.py src/cadrumo/core/errors/registry/_application_part1.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s231 src/cadrumo/application/review/tests/test_operator.py src/cadrumo/application/review/tests/test_filter.py src/cadrumo/entrypoints/cli/tests/test_error_registry_contract.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 -m "not unit" --basetemp .tmp/pytest-s231-nonunit src/cadrumo/application/review/tests/test_operator.py src/cadrumo/application/review/tests/test_filter.py src/cadrumo/entrypoints/cli/tests/test_error_registry_contract.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`
