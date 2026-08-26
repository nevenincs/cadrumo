---
generated: true
tags:
  - '#index'
  - '#profile-login-session'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:6cc68ee35b10d8ac8d5e89b502eed262b16d5a310e4acc282eb2a57b2ad737b4'
related:
  - '[[2026-07-24-profile-login-session-adr]]'
  - '[[2026-07-24-profile-login-session-close-honesty-review-audit]]'
  - '[[2026-07-24-profile-login-session-plan]]'
  - '[[2026-07-24-profile-login-session-research]]'
  - '[[2026-07-25-profile-login-session-model-facing-digest-delta-audit]]'
  - '[[2026-08-10-profile-login-session-stale-route-handover-code-review-audit]]'
---

# `profile-login-session` feature index

Auto-generated index of all documents tagged with `#profile-login-session`.

## Documents

### adr

- `2026-07-24-profile-login-session-adr` - `profile-login-session` adr: `canonical profile login/logout with persisted session custody` | (**status:** `superseded`)

### audit

- `2026-07-24-profile-login-session-close-honesty-review-audit` - `profile-login-session` audit: `Fresh-context campaign close honesty review`
- `2026-07-25-profile-login-session-model-facing-digest-delta-audit` - `profile-login-session` audit: `model facing digest delta`
- `2026-08-10-profile-login-session-stale-route-handover-code-review-audit` - `profile-login-session` audit: `Stale route handover code review`

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
- `2026-07-24-profile-login-session-W02-P04-S10` - Replace the root callback's implicit unlock with persisted-session resume (valid record resumes silently with one idle-deadline re-persist, absent or expired session makes non-exempt verbs refuse with a Notice naming aeat config login, CADRUMO_SECRET_PASSPHRASE headless path preserved process-scoped), verified by CLI lifecycle tests exercising resume, idle expiry, and absolute expiry against a real bucket
- `2026-07-24-profile-login-session-W02-P05-S11` - Register aeat config login (bootstrap-exempt, optional NAME argument, --secrets-stdin strict-JSON passphrase channel) and aeat config logout with envelope identifiers config.login and config.logout and the uniform result payloads, verified by documented-command and JSON-schema conformance plus direct invocation tests
- `2026-07-24-profile-login-session-W02-P05-S12` - Wire every new refusal and advisory through the typed error registry and Notice channel (expired-session, not-logged-in, throttle-wait, no-keychain persistence warning, cross-profile handover, idempotent no-op) and land all locale keys through the locales CLI in every catalogue, verified by the locale parity and translation-honesty gates plus the notice-conformance gate
- `2026-07-24-profile-login-session-W02-P05-S13` - Land the end-to-end CLI session lifecycle test (login, decrypting command without prompt in a fresh process, clock-driven idle expiry refusal, re-login, absolute-cap refusal, logout idempotence) using real processes and real storage with no mocks, gate is the module green plus zero prompts observed on the resumed invocation
- `2026-07-24-profile-login-session-W03-P06-S14` - Delete the switch command and config profile logout registrations and every removed spelling from the write-policy allowlist, error-registry default_suggestion fields, next_action builders, curated operator help, envelope identifiers, operator-harness documents, and MCP mirrors, verified by rg sweeps returning zero hits for the removed spellings plus the operator-harness drift gate green
- `2026-07-24-profile-login-session-W03-P06-S15` - Sever the environment source for cadrumo_active_profile so the field is populated only by --profile and override_settings, retarget the logout override refusal to the per-invocation --profile case, and sweep every string or doc naming CADRUMO_ACTIVE_PROFILE as an operating mechanism, verified by a settings test proving the env var no longer selects a profile and the existing override-refusal tests retargeted green
- `2026-07-24-profile-login-session-W03-P07-S16` - Regenerate and update every documentation surface for the new grammar (user docs via the documentation workflow, generated API stubs via python -m dev.docs.apidocs scaffold, docs sequences naming switch or profile logout), verified by scaffold --check clean, the Sphinx nitpicky build gate, and documented-command conformance green
- `2026-07-24-profile-login-session-W03-P07-S17` - Run the campaign close gates (full-tree collect-only, path-scoped quality gates, formal vaultspec-code-review dispatch) and the mandatory fresh-context honesty review persisted as a vault audit with every surfaced item tracked as a new step or formally deferred, gate is the honesty-review audit document existing before the campaign is declared structurally complete

### plan

- `2026-07-24-profile-login-session-plan` - `profile-login-session` plan

### research

- `2026-07-24-profile-login-session-research` - `profile-login-session` research: `profile login session: persisted cross-process profile sessions with login/logout`
