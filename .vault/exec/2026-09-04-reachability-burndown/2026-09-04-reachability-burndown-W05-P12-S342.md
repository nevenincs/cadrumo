---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:3f7fc21bcbb8b0c600e41adbe4c89257add140ad584f1e1890c4ff3e42db35dc'
step_id: 'S342'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the sensitive-persistence source-policy engine and its hand-maintained surface, call-site, and exception inventories.

## Scope

- `sensitive persistence policy test`
- `behavioral storage security suites`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/adapters/persistence/storage/tests/test_sensitive_persistence_policy.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/tests/test_secure_sql.py src/cadrumo/domain/invoices/tests/test_secure_storage_roundtrip.py src/cadrumo/domain/submission/tests/test_secure_storage_roundtrip.py src/cadrumo/application/modelo/tests/test_review_package.py src/cadrumo/application/user_profile/tests/test_recovery_custody.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
