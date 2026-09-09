---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:9cc09cde1e344e8743a873d44085aa2883b33c743923891d15f9cd3318b7ece9'
step_id: 'S234'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Remove the unused profile-bundle import-event metadata that describes an event no production path emits, while retaining the accepted bundle deserializer authority.

## Scope

- `src/cadrumo/application/user_profile/bundle.py`

## Changes

- `M` `src/cadrumo/application/user_profile/bundle.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/user_profile/bundle.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s234 src/cadrumo/application/user_profile/tests/test_bundle_encryption_kdf_window.py src/cadrumo/domain/user_profile/tests/test_portable_export_schema.py src/cadrumo/domain/user_profile/tests/test_portable_export_outer_instant.py src/cadrumo/domain/user_profile/tests/test_portable_export_instant_contract.py src/cadrumo/core/tests/test_persisted_version_single_declaration.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`
