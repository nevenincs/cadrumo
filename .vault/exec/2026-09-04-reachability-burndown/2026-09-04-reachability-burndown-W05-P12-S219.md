---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:374a493475e38e48cc586465394de6899ba8a87548eacfbefe8976e62af596a1'
step_id: 'S219'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Route concurrent custody-change subclasses ahead of record-integrity parents at the adapter and profile-repository boundaries, preserving retryable concurrency as port/transaction conflicts and translating permanent record corruption to the non-retryable transaction-corrupt owner; prove the type/AST-derived flattening gate returns clean.

## Scope

- `Profile custody adapter and committed-profile repository error translation`
- `focused custody/error tests`
- `handler-flattening detector teeth`
- `exact reachability signal`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/profile_custody.py`
- `M` `src/cadrumo/application/user_profile/profile_repository.py`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S219.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/persistence/storage/profile_custody.py src/cadrumo/application/user_profile/profile_repository.py src/cadrumo/tests/test_no_handler_flattens_a_divergent_retryability.py src/cadrumo/adapters/persistence/storage/tests/test_profile_custody_adapter.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s219 src/cadrumo/tests/test_no_handler_flattens_a_divergent_retryability.py src/cadrumo/adapters/persistence/storage/tests/test_profile_custody_adapter.py` -> `pass (9 passed)`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (expected nonzero with live findings: 62 unreachable modules, 311 exact unused symbols, 15 orphaned tests, 2029/2092 shipped modules reachable)`
