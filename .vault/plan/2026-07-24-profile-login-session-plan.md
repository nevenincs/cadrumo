---
tags:
  - '#plan'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-24'
tier: L3
related:
  - '[[2026-07-24-profile-login-session-adr]]'
  - '[[2026-07-24-profile-login-session-research]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `profile-login-session` plan

## Wave `W01` - Session core infrastructure

Land the adapter-layer session substrate: absolute cap on BucketSession, the session-wrapped-DEK persisted record with OS-keychain session-key custody, and the failed-login throttle, all with real-adapter roundtrip and anti-tautology proofs before any CLI surface changes.

### Phase `W01.P01` - BucketSession absolute cap

Give the in-process session an absolute deadline so a touched-forever session can no longer live past the cap, with the new lifetime configurable through Settings and the bucket manifest.

- [x] `W01.P01.S01` - Extend BucketSession with opened_at and an immutable absolute_deadline, clamp touch() so the sliding idle deadline never passes the absolute deadline and make is_expired plus evaluate_idle enforce both limits, verified by new real-clock adapter tests that prove a continuously-touched session still seals at the absolute cap; `src/cadrumo/adapters/persistence/storage/master_key/_bucket_session.py`.
- [x] `W01.P01.S02` - Add the cadrumo_bucket_default_session_absolute_minutes Settings field (default 240, validated 60 to 720) and the session_absolute_minutes bucket-manifest override with a resolver mirroring idle_minutes_for_bucket, threading the resolved cap into _provider_enter, verified by settings-validation tests and a provider-enter test observing the configured cap on the opened session; `src/cadrumo/core/config.py, src/cadrumo/adapters/persistence/storage/master_key/_master_key_bucket_dek.py, src/cadrumo/adapters/persistence/storage/master_key/_master_key.py`.

### Phase `W01.P02` - Persisted session record and keychain custody

Implement ADR Decision 3: the strict session record with AAD-bound metadata, the AES-256-GCM session-wrap of the bucket DEK under an ephemeral keychain-held session key, the fail-closed resume evaluation, and the roundtrip plus anti-tautology proof suite.

- [x] `W01.P02.S03` - Author the strict frozen session-record model (schema_version, bucket_id, backend kind as a core StrEnum, authenticated_at, idle_deadline, absolute_deadline, nonce, ciphertext, tag) plus AES-256-GCM session-wrap and unwrap of the DEK under a 32-byte session key with every metadata field bound as associated data and all buffers zeroised on every exit path, verified by unit tests proving any single AAD field mutation fails the tag check; `src/cadrumo/adapters/persistence/storage/master_key/_persisted_session.py, src/cadrumo/core (session enums)`.
- [x] `W01.P02.S04` - Implement OS-keychain session-key custody under service cadrumo:profile-session with account equal to the bucket UUID, reusing the existing backend probe so fail.Keyring and null.Keyring hosts mint no persisted session, verified by real-keyring set, get, delete, and absent-entry tests on the platform backend; `src/cadrumo/adapters/persistence/storage/master_key/_persisted_session.py`.
- [x] `W01.P02.S05` - Implement the session store (atomic secure write of session.v1 into the separated bucket keystore directory, delete, and a fail-closed resume evaluation that deletes and refuses on expiry, version mismatch, tamper, or an orphaned keychain entry), verified by targeted tests covering each refusal branch with the refusal reason asserted structurally; `src/cadrumo/adapters/persistence/storage/master_key/_persisted_session.py`.
- [x] `W01.P02.S06` - Land the roundtrip discipline suite for the persisted session (mint, save, fresh-process-shape load, strict model equality with every defaultable field non-default) plus the anti-tautology proofs (corrupt an on-disk deadline byte and assert refusal, delete the keychain entry and assert logged-out treatment, bump schema_version and assert delete-plus-refuse), gate is the new test module green under uv run --no-sync pytest; `src/cadrumo/adapters/persistence/storage/master_key/tests/test_persisted_session_roundtrip.py`.

### Phase `W01.P03` - Failed-login throttle

Persist the per-bucket failed-attempt counter and enforce the exponential backoff before any Argon2id derivation runs, per ADR Decision 5.

- [x] `W01.P03.S07` - Implement the per-bucket failed-login throttle sidecar (plaintext counts and timestamps only, exponential 2^n seconds capped at 60, evaluated before any Argon2id derivation, counter reset on success and on logout) with the wait surfaced in the refusal context, verified by tests driving consecutive failures through the real file backend and asserting the enforced delays and the reset; `src/cadrumo/adapters/persistence/storage/master_key/_login_throttle.py`.

## Wave `W02` - Login and logout services and CLI verbs

Build the application-layer login/logout orchestration on the W01 substrate, replace the root callback's implicit unlock with fail-closed session resume, and register the canonical `aeat config login` / `aeat config logout` verbs with Notice-channel refusals and locale coverage.

### Phase `W02.P04` - Login and logout application services

Compose the W01 substrate into the login orchestration (select, authenticate, mint) and the strong-close logout inside the existing pointer-transaction lock order, and replace the CLI root callback's implicit unlock with fail-closed persisted-session resume.

- [ ] `W02.P04.S08` - Build the login orchestration service (pointer transaction, optional NAME selection through the existing UUID-or-label resolver, backend authentication by unwrap, session-key mint, record persistence) that is idempotent-guarded for a still-valid same-profile session and closes the previous session with a Notice when the target differs, verified by application-layer tests over real storage covering first login, valid-session no-op retry, and cross-profile handover; `src/cadrumo/application/user_profile/_login_session.py`.
- [ ] `W02.P04.S09` - Extend logout_active_profile to the full strong close (seal and zeroise the live session, delete the persisted record and its keychain entry, release the bucket lockfile, clear the pointer) while staying idempotent when already logged out, verified by tests proving both artefacts are gone after logout and a second logout is a clean no-op; `src/cadrumo/application/user_profile/_orchestration.py`.
- [ ] `W02.P04.S10` - Replace the root callback's implicit unlock with persisted-session resume (valid record resumes silently with one idle-deadline re-persist, absent or expired session makes non-exempt verbs refuse with a Notice naming aeat config login, CADRUMO_SECRET_PASSPHRASE headless path preserved process-scoped), verified by CLI lifecycle tests exercising resume, idle expiry, and absolute expiry against a real bucket; `src/cadrumo/entrypoints/cli/__init__.py, src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`.

### Phase `W02.P05` - CLI verbs, notices, and locales

Register `aeat config login` and `aeat config logout`, wire every refusal through the typed error registry and Notice channel, and land the locale keys through the locales CLI with full four-catalogue parity.

- [ ] `W02.P05.S11` - Register aeat config login (bootstrap-exempt, optional NAME argument, --secrets-stdin strict-JSON passphrase channel) and aeat config logout with envelope identifiers config.login and config.logout and the uniform result payloads, verified by documented-command and JSON-schema conformance plus direct invocation tests; `src/cadrumo/entrypoints/cli/_config/_custody.py, src/cadrumo/entrypoints/cli/_config/__init__.py`.
- [ ] `W02.P05.S12` - Wire every new refusal and advisory through the typed error registry and Notice channel (expired-session, not-logged-in, throttle-wait, no-keychain persistence warning, cross-profile handover, idempotent no-op) and land all locale keys through the locales CLI in every catalogue, verified by the locale parity and translation-honesty gates plus the notice-conformance gate; `src/cadrumo/entrypoints/cli, src/cadrumo/locales (via python -m cadrumo.locales)`.
- [ ] `W02.P05.S13` - Land the end-to-end CLI session lifecycle test (login, decrypting command without prompt in a fresh process, clock-driven idle expiry refusal, re-login, absolute-cap refusal, logout idempotence) using real processes and real storage with no mocks, gate is the module green plus zero prompts observed on the resumed invocation; `src/cadrumo/entrypoints/cli/tests/test_profile_login_session_lifecycle.py`.

## Wave `W03` - Hard cutover, override retirement, and conformance

Delete `switch` and `config profile logout`, retire the CADRUMO_ACTIVE_PROFILE environment source, hand-sweep every unscanned suggestion surface, and close the campaign through the documented-command, JSON-schema, operator-harness, locale, docs, and full-tree gates.

### Phase `W03.P06` - Verb removal and override retirement

Hard-cut the retired doors: delete `switch` and `config profile logout` with the full unscanned-surface hand-sweep, and sever the CADRUMO_ACTIVE_PROFILE environment source while preserving the in-process override channel for --profile and tests.

- [ ] `W03.P06.S14` - Delete the switch command and config profile logout registrations and every removed spelling from the write-policy allowlist, error-registry default_suggestion fields, next_action builders, curated operator help, envelope identifiers, operator-harness documents, and MCP mirrors, verified by rg sweeps returning zero hits for the removed spellings plus the operator-harness drift gate green; `src/cadrumo/entrypoints/cli/_config/_custody.py, src/cadrumo/entrypoints/cli/_config/__init__.py, src/cadrumo/application/storage_write_policy.py, src/cadrumo/entrypoints/cli/operator_surface/_help.py, src/cadrumo/_data/agent`.
- [x] `W03.P06.S15` - Sever the environment source for cadrumo_active_profile so the field is populated only by --profile and override_settings, retarget the logout override refusal to the per-invocation --profile case, and sweep every string or doc naming CADRUMO_ACTIVE_PROFILE as an operating mechanism, verified by a settings test proving the env var no longer selects a profile and the existing override-refusal tests retargeted green; `src/cadrumo/core/config.py, src/cadrumo/core/_bucket_pointer_io.py, src/cadrumo/application/user_profile/_orchestration.py`.

### Phase `W03.P07` - Documentation and campaign close gates

Regenerate every documentation and conformance surface for the new grammar and close the campaign only through green gates plus the mandatory fresh-context honesty review.

- [ ] `W03.P07.S16` - Regenerate and update every documentation surface for the new grammar (user docs via the documentation workflow, generated API stubs via python -m dev.docs.apidocs scaffold, docs sequences naming switch or profile logout), verified by scaffold --check clean, the Sphinx nitpicky build gate, and documented-command conformance green; `docs/, dev/docs`.
- [ ] `W03.P07.S17` - Run the campaign close gates (full-tree collect-only, path-scoped quality gates, formal vaultspec-code-review dispatch) and the mandatory fresh-context honesty review persisted as a vault audit with every surfaced item tracked as a new step or formally deferred, gate is the honesty-review audit document existing before the campaign is declared structurally complete; `.vault/audit (campaign close)`.

## Description

This plan executes the profile-login-session ADR (all five decisions), grounded in the profile-login-session research. W01 delivers ADR Decisions 2, 3, and 5 at the adapter layer (absolute cap, session-wrapped-DEK persistence, throttle). W02 delivers Decisions 1 and 4's service half (login/logout orchestration, session resume, CLI verbs, notices). W03 delivers Decision 1's hard cutover (`switch` and `config profile logout` removal), Decision 4's environment-override retirement, and the documentation and conformance close. Executors are opus coders; every step is scoped for one dispatch. SAFETY: the shared-worktree destructive-git prohibition and the explicit-pathspec commit rule bind every dispatch, and vaultspec-rag discovery precedes every coding step.

## Steps

The tier-L3 structure (Waves W01 to W03, Phases P01 to P07, Steps S01 to S17) is serialized in the Wave blocks above by the plan CLI; all seventeen Step rows live there.

## Parallelization

Waves are strictly sequential: W02 composes W01's substrate, W03 removes doors only after W02's replacements are live (no window where neither `switch` nor `login` exists). Within W01, P01 and P03 may run in parallel; P02 depends on P01 (the record carries the absolute deadline P01 introduces). Within W02, P04's three steps are ordered (S08, S09, then S10) and P05 starts after S08 and S09 land. Within W03, P06's two steps may run in parallel, P07 is last. Steps sharing a scope file (S03, S04, S05 on `_persisted_session.py`) are serialized on one executor.

## Verification

Mission success criteria, each a verifiable check:

- A fresh process after `aeat config login` runs a decrypting verb with zero prompts (S13 lifecycle test observes no prompt).
- A continuously-touched session seals at the absolute cap, and an idle session seals at the idle window, each surfacing the instructive refusal naming `aeat config login` (S01, S10, S13).
- No plaintext KEK, DEK, or session-key bytes exist on disk at any point of the login/resume/logout cycle, proven by the S06 roundtrip suite's on-disk inspection, and every persisted-session refusal branch is anti-tautology proven (corrupt, orphan, version-bump).
- `rg` sweeps for `config switch`, `profile logout`, and `CADRUMO_ACTIVE_PROFILE`-as-operating-mechanism return zero production hits (S14, S15).
- Documented-command conformance, JSON-schema conformance, operator-harness drift gate, locale parity and honesty gates, apidocs `scaffold --check`, the Sphinx nitpicky build, and the full-tree collect-only gate are green with owner-triage recorded for any peer-owned red (S11, S12, S16, S17).
- Every completed step has an exec record, and the fresh-context honesty review audit exists before structural completion is declared (S17).
