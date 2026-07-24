---
generated: true
tags:
  - '#index'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-24'
related:
  - '[[2026-07-24-profile-login-session-W01-P01-S01]]'
  - '[[2026-07-24-profile-login-session-W01-P01-S02]]'
  - '[[2026-07-24-profile-login-session-W01-P02-S03]]'
  - '[[2026-07-24-profile-login-session-W01-P02-S04]]'
  - '[[2026-07-24-profile-login-session-W01-P02-S05]]'
  - '[[2026-07-24-profile-login-session-W01-P02-S06]]'
  - '[[2026-07-24-profile-login-session-W01-P03-S07]]'
  - '[[2026-07-24-profile-login-session-W02-P04-S08]]'
  - '[[2026-07-24-profile-login-session-W02-P04-S09]]'
  - '[[2026-07-24-profile-login-session-adr]]'
  - '[[2026-07-24-profile-login-session-plan]]'
  - '[[2026-07-24-profile-login-session-research]]'
---

# `profile-login-session` feature index

Auto-generated index of all documents tagged with `#profile-login-session`.

## Documents

### adr

- `2026-07-24-profile-login-session-adr` - `profile-login-session` adr: `canonical profile login/logout with persisted session custody` | (**status:** `accepted`)

### exec

- `2026-07-24-profile-login-session-W01-P01-S01` - Extend BucketSession with opened_at and an immutable absolute_deadline, clamp touch() so the sliding idle deadline never passes the absolute deadline and make is_expired plus evaluate_idle enforce both limits, verified by new real-clock adapter tests that prove a continuously-touched session still seals at the absolute cap
- `2026-07-24-profile-login-session-W01-P01-S02` - Add the cadrumo_bucket_default_session_absolute_minutes Settings field (default 240, validated 60 to 720) and the session_absolute_minutes bucket-manifest override with a resolver mirroring idle_minutes_for_bucket, threading the resolved cap into _provider_enter, verified by settings-validation tests and a provider-enter test observing the configured cap on the opened session
- `2026-07-24-profile-login-session-W01-P02-S03` - Author the strict frozen session-record model (schema_version, bucket_id, backend kind as a core StrEnum, authenticated_at, idle_deadline, absolute_deadline, nonce, ciphertext, tag) plus AES-256-GCM session-wrap and unwrap of the DEK under a 32-byte session key with every metadata field bound as associated data and all buffers zeroised on every exit path, verified by unit tests proving any single AAD field mutation fails the tag check
- `2026-07-24-profile-login-session-W01-P02-S04` - Implement OS-keychain session-key custody under service cadrumo:profile-session with account equal to the bucket UUID, reusing the existing backend probe so fail.Keyring and null.Keyring hosts mint no persisted session, verified by real-keyring set, get, delete, and absent-entry tests on the platform backend
- `2026-07-24-profile-login-session-W01-P02-S05` - Implement the session store (atomic secure write of session.v1 into the separated bucket keystore directory, delete, and a fail-closed resume evaluation that deletes and refuses on expiry, version mismatch, tamper, or an orphaned keychain entry), verified by targeted tests covering each refusal branch with the refusal reason asserted structurally
- `2026-07-24-profile-login-session-W01-P02-S06` - Land the roundtrip discipline suite for the persisted session (mint, save, fresh-process-shape load, strict model equality with every defaultable field non-default) plus the anti-tautology proofs (corrupt an on-disk deadline byte and assert refusal, delete the keychain entry and assert logged-out treatment, bump schema_version and assert delete-plus-refuse), gate is the new test module green under uv run --no-sync pytest
- `2026-07-24-profile-login-session-W01-P03-S07` - Implement the per-bucket failed-login throttle sidecar (plaintext counts and timestamps only, exponential 2^n seconds capped at 60, evaluated before any Argon2id derivation, counter reset on success and on logout) with the wait surfaced in the refusal context, verified by tests driving consecutive failures through the real file backend and asserting the enforced delays and the reset
- `2026-07-24-profile-login-session-W02-P04-S08` - Build the login orchestration service (pointer transaction, optional NAME selection through the existing UUID-or-label resolver, backend authentication by unwrap, session-key mint, record persistence) that is idempotent-guarded for a still-valid same-profile session and closes the previous session with a Notice when the target differs, verified by application-layer tests over real storage covering first login, valid-session no-op retry, and cross-profile handover
- `2026-07-24-profile-login-session-W02-P04-S09` - Extend logout_active_profile to the full strong close (seal and zeroise the live session, delete the persisted record and its keychain entry, release the bucket lockfile, clear the pointer) while staying idempotent when already logged out, verified by tests proving both artefacts are gone after logout and a second logout is a clean no-op

### plan

- `2026-07-24-profile-login-session-plan` - `profile-login-session` plan

### research

- `2026-07-24-profile-login-session-research` - `profile-login-session` research: `profile login session: persisted cross-process profile sessions with login/logout`
