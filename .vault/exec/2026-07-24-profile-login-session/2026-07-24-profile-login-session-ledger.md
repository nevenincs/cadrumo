---
tags:
  - '#exec'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:1048c5f6778af58d0e1ebc36eae3537a9666d74038ff919157d98704f5cac9bb'
related:
  - "[[2026-07-24-profile-login-session-plan]]"
---

# `profile-login-session` ledger

## Changes

- `S01` `T` `src/cadrumo/adapters/persistence/storage/master_key/_bucket_session.py`
- `S02` `T` `src/cadrumo/core/config.py`
- `S02` `T` `src/cadrumo/adapters/persistence/storage/master_key/_master_key_bucket_dek.py`
- `S02` `T` `src/cadrumo/adapters/persistence/storage/master_key/_master_key.py`
- `S03` `T` `src/cadrumo/adapters/persistence/storage/master_key/_persisted_session.py`
- `S03` `T` `src/cadrumo/core (session enums)`
- `S04` `T` `src/cadrumo/adapters/persistence/storage/master_key/_persisted_session.py`
- `S05` `T` `src/cadrumo/adapters/persistence/storage/master_key/_persisted_session.py`
- `S06` `T` `src/cadrumo/adapters/persistence/storage/master_key/tests/test_persisted_session_roundtrip.py`
- `S07` `T` `src/cadrumo/adapters/persistence/storage/master_key/_login_throttle.py`
- `S08` `T` `src/cadrumo/application/user_profile/_login_session.py`
- `S09` `T` `src/cadrumo/application/user_profile/_orchestration.py`
- `S10` `T` `src/cadrumo/entrypoints/cli/__init__.py`
- `S10` `T` `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`
- `S11` `T` `src/cadrumo/entrypoints/cli/_config/_custody.py`
- `S11` `T` `src/cadrumo/entrypoints/cli/_config/__init__.py`
- `S12` `T` `src/cadrumo/entrypoints/cli`
- `S12` `T` `src/cadrumo/locales (via python -m cadrumo.locales)`
- `S13` `T` `src/cadrumo/entrypoints/cli/tests/test_profile_login_session_lifecycle.py`
- `S14` `T` `src/cadrumo/entrypoints/cli/_config/_custody.py`
- `S14` `T` `src/cadrumo/entrypoints/cli/_config/__init__.py`
- `S14` `T` `src/cadrumo/application/storage_write_policy.py`
- `S14` `T` `src/cadrumo/entrypoints/cli/operator_surface/_help.py`
- `S14` `T` `src/cadrumo/_data/agent`
- `S15` `T` `src/cadrumo/core/config.py`
- `S15` `T` `src/cadrumo/core/_bucket_pointer_io.py`
- `S15` `T` `src/cadrumo/application/user_profile/_orchestration.py`
- `S16` `T` `docs/`
- `S16` `T` `dev/docs`
- `S17` `T` `.vault/audit (campaign close)`
