---
tags:
  - '#adr'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:0a2bf0499c4a8b8ce778001ad95bf95cdc412f73f98be55d7a950d7136bfe31f'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-adr]]"
  - "[[2026-05-14-secure-backend-passkey-custody-adr]]"
  - "[[2026-06-10-cli-operator-surface-adr]]"
  - '[[2026-07-24-profile-login-session-research]]'
---
# `profile-login-session` adr: `canonical profile login/logout with persisted session custody` | (**status:** `accepted`)

## Problem Statement

A taxpayer cannot "log in once and stay logged in". The profile-unlock session is a purely in-process `BucketSession` bound to a `ContextVar`; every `aeat` invocation is a fresh process, so the file backend re-prompts for the passphrase (or reads `CADRUMO_SECRET_PASSPHRASE`) on every command while the keyring backend silently re-derives with no explicit authentication gate at all. There is no absolute session cap (a touched-forever session never expires), no password-gated `login` verb, and no persisted session surviving across processes. Operators work around this by exporting `CADRUMO_ACTIVE_PROFILE` — a dev/test override that also blocks `logout` (`ProfileLogoutOverrideError`) and was never meant as the operating mechanism. Operator directive (2026-07-24): industry-standard, fintech-conformant profile login/logout; login once, auto-refresh on activity, expire on idle and on an absolute cap (~3–4 h suggested) or explicit logout; no environment variable required to operate; `login`/`logout` canonical, `switch` at most a selector.

## Prior-decision reconciliation

- `2026-07-15-cli-authority-verb-conformance-adr` (accepted). AMENDED by operator override. Its Decision 2 profile-logout strong-close semantics (close and zeroise the `BucketSession`, clear any OS-keystore session cache entry, release the lockfile, clear the pointer) are UPHELD verbatim and become `aeat config logout`. Its Decision 3 verb set is amended: `aeat config switch NAME` and `aeat config profile logout` are removed; `aeat config login [NAME]` and `aeat config logout` replace them as the canonical doors. Its one-verb, no-alias, hard-cutover rule is UPHELD — `switch` is deleted, not aliased. Everything else in that ADR stands.
- `2026-05-14-secure-backend-passkey-custody-adr` (accepted). Its custody selection A.II — passphrase-primary with an OS-keystore session cache and idle auto-lock — is REALISED here, upgraded from an unimplemented opt-in KEK cache to a default-on split-knowledge construction (session-wrapped DEK, Decision 3). Its `config lock`/`config unlock` verbs stay retired (already removed by the verb-conformance ADR); its Argon2id, enrollment, recovery, and copy-deck decisions stand.
- `2026-06-10-cli-operator-surface-adr` D1 (restore an intent-named switch verb): superseded on the verb only — the intent ("change to another taxpayer profile") is now expressed by `login NAME`.
- Provider auth `aeat config auth login/logout/reset` is a DIFFERENT concept (AEAT/Google provider sessions) and is untouched; the collision is resolved by namespace (Decision 1).
- Project rules this ADR must and does satisfy: `sensitive-financial-data-secure-storage-only` (no plaintext key material on disk — Decision 3), `aeat-safety-legal-gates` (no live-write surface touched), `no-legacy-compatibility` (hard cut: delete `switch`, delete the env-sourced override, no shims), `aeat-architecture-boundaries` (two root families preserved, closed sets as core enums, typed pydantic boundaries), `cli-notices-are-the-only-diagnostic-channel` (all advisories via `Notice`), `aeat-roundtrip-discipline` (persisted record ⇒ real-adapter roundtrip + anti-tautology proof), `single-subject-mutation-is-idempotent-guarded` (login/logout retry semantics), `compatibility-lifecycle-checkpoint` (Decision 3 states the session record's exemption rationale), `cadrumo-product-authority-names` (new keychain entries under `cadrumo:`), `aeat-spanish-stem-naming` (login/logout/session are generic computing vocabulary — permitted English).

## Considerations

- Grounding: `2026-07-24-profile-login-session-research` — current-state file/line inventory, web-cited baselines (OWASP Session Management, NIST SP 800-63B r3/r4 AAL2, OWASP Argon2id minimums, 1Password/KeePassXC/Bitwarden auto-lock defaults), and the three-option threat-model analysis.
- The DEK is symmetric key material: a persisted session may never place DEK/KEK plaintext (or anything derivable into them without a second factor) on disk.
- The OS keychain is the platform's secrets-at-rest surface and already custodies the keyring-backend master key; using it for an *ephemeral* session key adds no new trust anchor.
- An attacker running as the logged-in OS user defeats any local session scheme (they can read the keychain), exactly as they defeat an unlocked desktop password manager; the defensible bound is expiry (idle + absolute) plus explicit logout, not OS-user isolation.
- Argon2id at the current parameters (19 MiB / t=2 / p=1) is the OWASP-current minimum and stays.
- A CLI is invoked in bursts; the idle window must survive a coffee break but not a lunch break; the absolute cap must survive a filing session but not a workday left unattended.

## Considered options

### Option i: persisted session-marker record only (prompt-gating)

Rejected as the sole mechanism. It cannot deliver login-once on the file backend (nothing re-derives the KEK without the passphrase); on the keyring backend it is a policy gate only. Its typed-record shape (timestamps, expiry predicate, explicit teardown — mirroring `PersistedAuthSession`) is retained inside the chosen option.

### Option ii: DEK wrapped under an ephemeral OS-keychain session key (split knowledge)

CHOSEN. Login mints a random 32-byte session key SK, stores SK only in the OS keychain, and persists on disk only an AES-256-GCM wrap of the bucket DEK under SK with the session metadata bound as associated data. Disk-only attacker: ciphertext only. Keychain-only attacker: SK alone is useless. Deadline tampering: breaks the GCM tag. Both backends get login-once. Full threat model in the research.

### Option iii: keychain-held key with opaque on-disk handle

Rejected. The keychain entry alone is usable key material (a credential-store leak is a key leak), and expiry is policy-only — nothing cryptographically binds the deadlines to the key. Strictly weaker than option ii at equal complexity.

## Constraints

- No plaintext KEK/DEK/SK bytes under any project directory, log, or temp file at any time; in-memory buffers zeroise via the existing `_zeroise` boundary.
- Fail closed everywhere: expired, tampered, version-mismatched, or keychain-orphaned session artefacts are deleted and the verb refuses with an instructive `Notice`; no silent re-prompt fallback inside a non-login verb.
- The CLI root surface stays `config` + `app`; login/logout land under `config`. Closed value sets (session state, backend kind) are core `StrEnum`s.
- The pointer transaction lock order (pointer first, then bucket/session) is preserved; login/logout acquire the pointer transaction exactly as `select_profile_with_lifecycle_span`/`logout_active_profile` do today.
- Tests are real-adapter: real keyring backend where the platform provides one, real files, real SQLite, strict save→load→equality roundtrips with every defaultable field non-default, plus anti-tautology proofs (corrupt the record on disk, delete the keychain entry) per `aeat-roundtrip-discipline`.
- No live AEAT surface is touched; this is local custody only (`aeat-safety-legal-gates`).
- Hard cutover: every removed spelling (`switch`, `profile logout`, env-var operation) is swept from help surfaces, error-registry `default_suggestion`s, `next_action` builders, curated operator help, envelope `command=` identifiers, operator-harness documents, locales (via the locales CLI), and docs — the same hand-sweep surface the `aeat-cli-pull-and-file-standard` rule names, plus the `operator-harness-cites-live-cli-surface` drift gate.

## Implementation

### Decision 1 — canonical verb grammar and placement

```text
aeat config login [NAME] [--secrets-stdin]   # select (optional) + authenticate + mint persisted session
aeat config logout                            # strong session close (verb-conformance Decision 2 semantics)
```

- `login NAME` resolves NAME through the existing unambiguous UUID-or-exact-label resolver (including `sandbox:<name>`), writes the pointer inside the pointer transaction, authenticates, and mints the persisted session. `login` with no NAME authenticates the already-selected profile; with no selection it refuses naming `login NAME`.
- Authentication means: file backend — no-echo passphrase prompt (or `--secrets-stdin` strict-JSON `{"passphrase": ...}` for non-interactive use, same contract shape as the custody verbs; `CADRUMO_SECRET_PASSPHRASE` remains the headless env channel); keyring backend — the OS keychain unlock (Hello / Touch ID / Secret Service prompt) IS the authentication gate. Both paths verify by unwrapping (`MasterKeyPassphraseMismatchError` on failure); no comparison of secret strings, so verification is constant-time by construction (AEAD tag check).
- `logout`: close + zeroise the live `BucketSession` if any, delete the persisted session record and its keychain entry, release the bucket lockfile, clear the pointer — idempotent when already logged out (info `Notice`).
- `switch` is DELETED (no alias, no hidden registration, per the one-verb rule). `config profile logout` is DELETED (replaced by `config logout`). Provider auth keeps `config auth login/logout/reset` untouched; help text for both surfaces cross-names the other ("profile session" vs "AEAT provider session") so the namespace disambiguates.
- `login` is registered bootstrap-exempt (it must run without an active session); it is idempotent-guarded: a `login` for a profile whose persisted session is still valid returns the existing session as a no-op with an info `Notice` (no re-prompt, no new record); `login NAME` for a DIFFERENT profile closes the previous session (Notice) and proceeds.

### Decision 2 — session lifetimes (typed, configurable, fail-closed)

| Control | Default | Range (validated) | Config surface | Boundary behavior |
|---|---|---|---|---|
| Idle timeout (sliding) | 15 min | 5–60 min | existing `cadrumo_bucket_default_idle_lock_minutes` + manifest `idle_lock_minutes` | refreshed on each authorized storage access (existing `_check_session_freshness` touch) and re-persisted once per process at session resume; expiry seals the session, invalidates the record, next verb refuses citing `aeat config login` |
| Absolute cap | 240 min (4 h) | 60–720 min (12 h hard ceiling, NIST AAL2 r3) | new `cadrumo_bucket_default_session_absolute_minutes` + manifest `session_absolute_minutes` | fixed at login (`authenticated_at + cap`); never refreshed; idle refresh clamps to it; expiry = same refusal path |
| Failed-login backoff | exponential 2^n s, cap 60 s | not configurable | none | per-bucket plaintext throttle sidecar (counts + timestamps only, no secrets); counter resets on success and on logout; no permanent lockout (self-DoS on a local CLI is worse than throttled retry, NIST 800-63B §5.2.2 throttling satisfied) |

Justification is web-cited in the research: idle 15 min sits in OWASP's 15–30 band and equals KeePassXC's default; 4 h is the bottom of OWASP's 4–8 h workday band, inside every NIST AAL2 ceiling, and matches the operator's 3–4 h suggestion. `BucketSession` gains `opened_at` and `absolute_deadline`; `touch()` clamps the idle deadline to the absolute deadline; `is_expired()` and `evaluate_idle` check both. The provider-auth 18-min TTL is AEAT's own portal semantics and stays separate.

### Decision 3 — persisted session custody: session-wrapped DEK (option ii)

- At successful authentication, mint SK (32 random bytes), store it in the OS keychain under service `cadrumo:profile-session`, account = bucket UUID (product-authority naming; the legacy `aeat:secure-persistence` master-key entry keeps its pre-rule name).
- Persist `session.v1` in the bucket's separated keystore directory (beside the wrapped `bucket.dek`, wiped with the bucket): a strict pydantic record `{schema_version, bucket_id, backend_kind, authenticated_at, idle_deadline, absolute_deadline, nonce, ciphertext, tag}` where the ciphertext is AES-256-GCM(DEK) under SK and every metadata field is bound as associated data — tampering any deadline or the bucket id breaks the tag. Written via the existing atomic secure-write helper with restrictive permissions.
- Session resume (CLI root callback): read record → strict-validate → check `schema_version` (mismatch ⇒ delete + refuse-to-resume, forcing re-login; a session record is a revocable cache whose loss costs one re-login, never data — the stated, deliberate exemption from `compatibility-lifecycle-checkpoint` format enrollment, documented in the record's module) → check both deadlines fail-closed → fetch SK from the keychain (absent entry ⇒ treat as logged out, delete record) → unwrap DEK in memory → open `BucketSession` carrying the record's `authenticated_at`/`absolute_deadline` → advance and re-persist the idle deadline once. All key buffers zeroised on every failure path.
- Explicit non-goals: SK never wraps the KEK (the DEK suffices for column crypto; the KEK stays login-scoped); no session artefact ever lands outside the bucket keystore dir or the OS keychain; crash-stale records need no cleanup daemon — they expire by clock, are replaced by the next login, and are removed by logout/bucket-delete.
- Hosts with no usable keychain (probed `fail.Keyring`/`null.Keyring`): no persisted session is minted; `login` succeeds for the process and emits a warning `Notice` stating the session cannot persist and naming `CADRUMO_SECRET_PASSPHRASE` for headless use. Fail-closed beats writing key material to disk.

### Decision 4 — active-profile state standardization and env-override retirement

- The operating model becomes: pointer file = WHO is selected; persisted session = WHETHER they are authenticated; `BucketSession` = the in-process materialisation. One writer each: pointer via the pointer transaction, session record via the new session service, `BucketSession` via the provider enter/exit boundary.
- `CADRUMO_ACTIVE_PROFILE` is retired as an environment surface: the `cadrumo_active_profile` Settings field stops reading from the environment and becomes the in-process override channel only (populated by the `--profile` flag and `override_settings` in tests). The precedence chain, the database-route validator, `_config_storage_route`, and profile-health keep reading the field — their code is unchanged; only the env source is severed. Documentation and error strings that name the env var are swept. `logout`'s override refusal narrows to the `--profile` per-invocation case (unchanged semantics, retargeted message).
- The CLI root callback's implicit unlock is retired: non-exempt verbs resume a valid persisted session or refuse with an instructive `Notice` naming `aeat config login`; only `login` prompts. Headless/CI: `CADRUMO_SECRET_PASSPHRASE` + `--profile` keep working without any pointer or persisted session (process-scoped, exactly today's file-backend behavior — this is the sanctioned env surface, for secrets, not selection).

### Decision 5 — security hardening bundle

- Argon2id stays at the OWASP-current minimum (19 MiB / t=2 / p=1, salt 16, v2 params) — re-validated against the OWASP Password Storage Cheat Sheet in the research; the params file remains version-gated.
- Constant-time verification: authentication outcome derives solely from AEAD unwrap success; no secret-dependent branching or string comparison is introduced; the refusal message is identical for wrong-passphrase across buckets.
- Zeroisation: SK, KEK, and DEK buffers ride the existing `bytearray` + `_zeroise` contract, including on every early-return/exception path of login, resume, and logout; documented honestly (Python best-effort, as the `BucketSession` docstring already states).
- Throttle: Decision 2's backoff sidecar; the throttle is evaluated BEFORE the Argon2id derivation so an attacker cannot use the KDF as an oracle-free timing channel; refusals carry remaining-wait seconds in the `Notice` context.
- Crash-stale sessions: covered by clock expiry + atomic writes; an interrupted login leaves either no record or a complete record (atomic replace), never a torn one.
- Every refusal in this surface routes through the typed error registry + `Notice` channel with a concrete next verb (`aeat config login`, `aeat config logout`, `aeat config recover`) per `cli-notices-are-the-only-diagnostic-channel`.

## Rationale

Option ii is the only mechanism that delivers the operator's login-once requirement on both custody backends while keeping every on-disk byte ciphertext and making expiry tamper-evident; it needs two independent artefacts (keychain entry + disk record) to reconstruct the DEK, so a leak of either alone is harmless. It realises the custody direction the passkey-custody ADR already accepted (OS-keystore session cache) in a strictly stronger construction, and it inherits its record discipline from the proven `PersistedAuthSession` shape. The verb amendment follows the operator's explicit override; deleting `switch` rather than aliasing it preserves the one-verb rule the operator-surface ADR established and this project enforces by conformance gate. The timing defaults are each the conservative end of a cited industry band rather than invented numbers.

## Consequences

- Operators log in once per work session; every subsequent `aeat` command resumes silently until 15 min idle or 4 h absolute, then a single instructive refusal points at `aeat config login`. No environment variable is needed to operate.
- `switch` and `config profile logout` disappear (hard cut, pre-release); scripts using them break intentionally; all repository-owned consumers (docs, harness, locales, conformance inventories, MCP mirrors) move in the same campaign.
- The keyring backend gains an explicit authentication gate it never had (today it unlocks silently on every command); this is a deliberate UX change: the OS keychain prompt happens at `login`, not per command.
- Two new persisted artefacts per bucket (session record, throttle sidecar) and one keychain entry — all revocable caches, deleted by logout and bucket removal; no durability-floor obligations.
- New failure modes are all fail-closed refusals with next-verb guidance; the bare-invocation landing card and bootstrap-exempt flows are unaffected.
- Follow-up (out of scope): surfacing session state in `config profile status`, and any future TPM/DPAPI-NG hardening of the keychain anchor.
