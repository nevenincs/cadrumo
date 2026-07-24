---
tags:
  - '#exec'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S04'
related:
  - "[[2026-07-24-profile-login-session-plan]]"
---

# Implement OS-keychain session-key custody under service cadrumo:profile-session with account equal to the bucket UUID, reusing the existing backend probe so fail.Keyring and null.Keyring hosts mint no persisted session, verified by real-keyring set, get, delete, and absent-entry tests on the platform backend

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_persisted_session.py`

## Description

- Implement OS-keychain session-key custody: `store_profile_session_key` (round-trip verified write), `load_profile_session_key` (absent-entry None, malformed entry deleted and treated absent), `delete_profile_session_key` (idempotent best-effort) under service `cadrumo:profile-session`, account = bucket UUID.
- Reuse the canonical `KeyringMasterKeyProvider` backend probe so `fail.Keyring` / `null.Keyring` hosts refuse before any custody write.

## Outcome

Landed in commit `6a0fe2224e`. `TestKeychainCustody` exercises the real platform backend (Windows Credential Manager `WinVaultKeyring`) for set/get/delete/absent/malformed with random per-test accounts and full cleanup.

## Notes

The legacy `aeat:secure-persistence` master-key entry is untouched; only the new session surface uses the `cadrumo:` product-authority service name.
