---
tags:
  - '#exec'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:b8d5b26b6f02d096c9cbe0510af14c9c6a4b7c8739354fbfb984021dd5c3b7f2'
step_id: 'S03'
related:
  - "[[2026-07-24-profile-login-session-plan]]"
---

# Author the strict frozen session-record model (schema_version, bucket_id, backend kind as a core StrEnum, authenticated_at, idle_deadline, absolute_deadline, nonce, ciphertext, tag) plus AES-256-GCM session-wrap and unwrap of the DEK under a 32-byte session key with every metadata field bound as associated data and all buffers zeroised on every exit path, verified by unit tests proving any single AAD field mutation fails the tag check

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_persisted_session.py`
- `src/cadrumo/core (session enums)`

## Description

- Author `PersistedProfileSession` (strict frozen, extra=forbid) carrying schema_version, bucket_id, `SecretStoreBackend` backend kind, three UTC-validated deadlines, and the 12/32/16-byte nonce/ciphertext/tag in `src/cadrumo/adapters/persistence/storage/master_key/_persisted_session.py`.
- Implement `wrap_profile_session_dek` / `unwrap_profile_session_dek`: AES-256-GCM over the 32-byte DEK under a 32-byte session key with canonical-JSON AAD binding every metadata field; idle-past-absolute and naive datetimes refused.
- Add the core closed set `ProfileSessionRefusalReason` in `src/cadrumo/core/_profile_session.py`, exported through the core facade.
- Add `advance_profile_session_idle_deadline` (fresh-nonce re-wrap, clamped to the absolute cap, DEK buffer zeroised).

## Outcome

Landed in commit `6a0fe2224e`. The AAD-mutation matrix (`TestSessionWrapAadMatrix`) proves each of the six metadata fields plus ciphertext and tag individually fail tag verification; ruff clean; 260-test master_key tree green.

## Notes

Zeroisation is the documented Python best-effort contract: AEAD and pydantic boundaries require transient immutable bytes views; the steady-state buffers are `bytearray`s wiped on every exit path.
