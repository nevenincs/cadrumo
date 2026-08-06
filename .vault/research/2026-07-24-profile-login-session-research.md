---
tags:
  - '#research'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:3b8e5a1f3d30b4018560b4b17c05c26caa6759ceb8aad3d9ee1946b5d9619ef0'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-adr]]"
  - "[[2026-05-14-secure-backend-passkey-custody-adr]]"
  - "[[2026-06-10-cli-operator-surface-adr]]"
---

# `profile-login-session` research: `profile login session: persisted cross-process profile sessions with login/logout`

Operator directive: users must log in to a profile once with a password, stay logged in across `aeat` invocations until explicit logout or timeout, and operate the CLI without setting any environment variable (`CADRUMO_ACTIVE_PROFILE` is a dev/test workaround, to be retired as the operating mechanism). `login`/`logout` are the verbs users understand; `switch` becomes at most a selector. This research grounds the current session/custody surfaces, derives web-cited fintech-grade timing and hardening baselines, and analyses three candidate mechanisms for a cross-process session that never persists raw key material to disk. The evidence favors a session-wrapped DEK under an OS-keychain-held ephemeral session key; the ADR decides.

## Findings

### The profile-unlock session is purely in-process and evaporates between commands

`BucketSession` (`src/cadrumo/adapters/persistence/storage/master_key/_bucket_session.py:51`) holds the unlocked KEK and DEK in `bytearray` buffers, zeroised at `close()` (`_bucket_session.py:259`). It is bound per-thread via a `ContextVar` (`_active_session.py:48`) and activated by the CLI root callback `_activate_active_bucket_session` (`src/cadrumo/entrypoints/cli/__init__.py:396`) on every non-bootstrap-exempt invocation via `get_master_key_provider()` as a context manager. Each `aeat` invocation is a fresh process, so the session never survives a command. An `atexit` hook zeroises on interpreter exit (`_active_session.py:178`).

Idle timeout exists but only in-process: `BucketSession` carries `_idle_window`/`_idle_deadline`, sliding `touch(now)` (`_bucket_session.py:191`) and `is_expired(now)` (`_bucket_session.py:197`); `evaluate_idle` (`_idle_timeout.py:43`, `DEFAULT_IDLE_LOCK_MINUTES = 15`) is enforced by `SecureObjectRepository._check_session_freshness` (`src/cadrumo/adapters/persistence/storage/sql/secure_objects.py:217`), the sole production `touch()` caller, raising `SessionExpiredError` on expiry. Config: `Settings.cadrumo_bucket_default_idle_lock_minutes` (default 15) with per-bucket manifest override `idle_lock_minutes` (`_master_key_bucket_dek.py:49`, `idle_minutes_for_bucket`).

Genuinely absent (confirmed by direct read, no RAG hit and no `rg` hit for a persisted profile session or keystore session cache):

- Any persisted profile session surviving across CLI processes. The `secure-backend-passkey-custody` ADR's opt-in "OS-keystore session cache" (its decision 5) was never implemented — no `keystore_session_cache` setting exists in `src/cadrumo/core/config.py`.
- An absolute session cap: `BucketSession` stores no `opened_at`; a touched-forever session never expires.
- A password-gated profile `login` verb: unlock is an implicit side-effect of the root callback. The file backend re-prompts (or reads `CADRUMO_SECRET_PASSPHRASE`) every process (`_master_key.py:427` `_resolve_passphrase`); the keyring backend re-derives silently from the OS keychain (`_master_key.py:244`).

### Master-key custody chain (what a session must guard)

File backend: passphrase → Argon2id KEK (`_master_key_derivation.py:12`: memory 19 MiB, time 2, parallelism 1, salt 16 B, `KDF_PARAMS_VERSION = 2` — exactly the OWASP current minimum, see baselines below) → unwraps `master.key` (AES-256-GCM, AAD `cadrumo.master-key.v1`); wrong passphrase raises `MasterKeyPassphraseMismatchError` (`_master_key.py:586`). NIST verifier minimum length 8 is enforced (`_master_key.py:110`, `PassphraseTooShortError`). Keyring backend: 32-byte master key stored under service `aeat:secure-persistence` account `master` (`_master_key.py:116`); OS keychain owns the unlock UX. Either way the master key acts as bucket KEK: `load_or_mint_bucket_dek` (`_master_key_bucket_dek.py:64`) unwraps the per-bucket DEK from the separated keystore path (`bucket_dek_path`, keystore-separation validated). `_provider_enter` (`_master_key.py:794`) composes the whole chain per process and opens the `BucketSession`.

Consequence for design: a persisted session must let a fresh process reach the bucket DEK without re-prompting, without writing DEK/KEK plaintext to disk (rule `sensitive-financial-data-secure-storage-only`).

### Active-profile pointer and the env override

Precedence chain (`src/cadrumo/core/_bucket_pointer_io.py:145`, `resolve_active_bucket_id`): `Settings.cadrumo_active_profile` (populated from the `CADRUMO_ACTIVE_PROFILE` env var or `override_settings`, also the `--profile` flag's internal channel via `entrypoints/cli/__init__.py:294`) wins over the plaintext pointer file `<root>/active-profile`. The override is additionally read by the database-route validator (`core/config.py:985`), `core/_config_storage_route.py:102`, and workflow profile-health (`application/workflow/_profile_health.py:178`). `logout_active_profile` (`application/user_profile/_orchestration.py:477`) refuses while the override is set (`ProfileLogoutOverrideError`) because a process-scoped env override cannot be unset by the application boundary. Pointer mutation is serialised by the reentrant fail-closed pointer transaction (`application/user_profile/_profile_pointer_transaction.py:115`).

Retirement surface: the env var is one pydantic-settings field; the internal `override_settings` channel must survive (it is how `--profile` and tests scope a selection in-process), so retirement means removing the environment *source* for the field, not the field.

### Reusable pattern: the provider-auth persisted session

`PersistedAuthSession` (`application/auth/_sessions.py:171`) is a persisted, encrypted, timestamped session for AEAT provider auth: `{provider_kind, identity_nif, authenticated_at, idle_deadline, is_expired(now)}`, provider metadata persisted through the encrypted outbound session store; idle TTL 18 minutes mirroring AEAT's own portal window (`adapters/outbound/aeat/auth/_clave_movil.py:295` refreshes on successful probe). `logout_operator_auth` (`application/auth/_operator.py:756`) clears sessions while preserving provider config. This proves the shape (typed record, timestamps, idle deadline, explicit logout) but not the custody: provider sessions guard cookies; a profile session guards a symmetric DEK, so the record alone cannot carry the secret.

### Governing decisions to reconcile

- `2026-07-15-cli-authority-verb-conformance-adr` (accepted): declares `switch` = select-and-unlock, `config profile logout` = strong session-close ("close and zeroise the active BucketSession, clear any OS-keystore session cache entry, release its lockfile, and clear the pointer"), no `login` verb, one-verb rule with hard cutover and no aliases. The operator directive now overrides the verb choice (login/logout canonical); the strong-close semantics and the one-verb/no-alias rule remain good.
- `2026-05-14-secure-backend-passkey-custody-adr` (accepted, amended by the above): selected custody option A.II "passphrase-primary with OS-keystore session cache", i.e. an OS-keystore-cached KEK with idle auto-lock was ALREADY ACCEPTED as an opt-in; it was never built, and its `config lock`/`config unlock` verbs were later removed by the verb-conformance ADR. The new design can land as the (now mandatory-by-default) realisation of that accepted custody direction, with a stronger split-knowledge construction (see options below).
- `2026-06-10-cli-operator-surface-adr` D1: restored an intent-named profile-switch verb. Affected by `switch` retirement.
- Naming collision: `aeat config auth login`/`logout` already exist for provider (AEAT) auth (`entrypoints/cli/_config/_auth.py:255,302`). The profile session is a different concept; placement must disambiguate.
- `compatibility-lifecycle-checkpoint`: a new persisted format normally enrolls floor/version/lineage at birth. A session record is a revocable cache (loss costs one re-login, never data), so refusal-and-delete on version mismatch is the honest posture — the ADR must state this explicitly.

### Web-cited timing and hardening baselines

| Control | Source | Cited guidance |
|---|---|---|
| Idle timeout | OWASP Session Management Cheat Sheet | 2–5 min high-value apps, 15–30 min low-risk apps |
| Absolute timeout | OWASP Session Management Cheat Sheet | 4–8 h for a full-workday application |
| Reauthentication cap | NIST SP 800-63B (rev 3) AAL2 | reauth at least once per 12 h regardless of activity, and after ≥ 30 min inactivity |
| Reauthentication cap | NIST SP 800-63B-4 AAL2 | absolute SHOULD ≤ 24 h, inactivity SHOULD ≤ 1 h |
| Argon2id | OWASP Password Storage Cheat Sheet | minimum m=19 MiB, t=2, p=1 (matches `_master_key_derivation.py:12`) |
| Desktop auto-lock defaults | 1Password support docs | lock after system idle 10 min (default) |
| Desktop auto-lock defaults | KeePassXC (keepassxreboot/keepassxc PR #12689) | idle lock default 15 min, lock-on-idle now default-on |
| Desktop auto-lock defaults | Bitwarden vault-timeout docs | client vault timeout defaults ~15 min / on restart, action "lock" |
| Failed-attempt throttling | NIST SP 800-63B §5.2.2 | limit consecutive failed attempts (≤100 aggregate), rate-limiting/backoff sanctioned |

Derived recommendation (single numbers, justified range): **idle 15 min** (keep the existing default — inside OWASP's 15–30 band, equal to KeePassXC's default, near 1Password's 10; a local encrypted tax vault is closer to a password manager than to a banking web session, and the existing per-bucket override already lets a cautious operator go to 5); **absolute cap 240 min (4 h)** (bottom of OWASP's 4–8 h workday band, inside every NIST AAL2 ceiling, matches the operator's suggested 3–4 h; configurable 60–720 min with 12 h as the hard ceiling per NIST AAL2 rev 3); **failed-login backoff** exponential 2^n s capped at 60 s with the counter persisted per bucket and reset on success (Argon2id already imposes ~50–100 ms per attempt; a hard lockout is rejected as self-DoS on a local CLI).

### Session-persistence mechanism options

Threat model axes: (T1) attacker with disk read only (stolen backup, other OS user reading files); (T2) attacker running as the logged-in OS user (can read the OS keychain and disk); (T3) tampering with the persisted record (deadline extension, bucket swap).

**Option i — persisted session-marker record only.** Mirror `PersistedAuthSession`: an encrypted/authenticated record `{bucket_id, authenticated_at, idle_deadline, absolute_deadline}` that gates whether the CLI *prompts*, while the key is still re-derived per process (keyring backend: silently from the keychain; file backend: from the passphrase). T1: safe, nothing but timestamps. T3: mitigable by MAC. Fatal gap: on the file backend there is nothing to re-derive the KEK from without the passphrase, so "login once" is simply not delivered — the marker only works where the keychain already silently unlocks, where it adds policy value (an explicit login gate over today's implicit unlock) but no custody value. Rejected as the sole mechanism; its *record shape* survives inside options ii/iii.

**Option ii — DEK wrapped under an ephemeral session key held in the OS keychain (split knowledge).** At login: derive KEK (passphrase or keychain master key), unwrap the bucket DEK, mint a random 32-byte session key SK, store SK in the OS keychain under a per-bucket entry (`cadrumo:profile-session` / bucket UUID), persist a session record in the bucket keystore dir: AES-256-GCM ciphertext of the DEK under SK, with `{version, bucket_id, backend kind, authenticated_at, idle_deadline, absolute_deadline}` bound as associated data. A fresh process reads the record, checks expiry fail-closed, fetches SK from the keychain, unwraps the DEK in memory, opens a `BucketSession`. Logout/expiry deletes both artefacts and zeroises. T1: disk yields only a GCM blob — strictly no worse than the already-persisted wrapped `bucket.dek`; no plaintext key material on disk, satisfying `sensitive-financial-data-secure-storage-only`. T2: an attacker as the logged-in OS user can combine keychain+disk and unlock — exactly the posture of the accepted keyring master-key backend and of every desktop password manager's unlocked state; bounded by idle+absolute expiry and logout. Keychain-leak-only (backup of the credential store without the disk record): SK alone is useless — strictly stronger than caching the KEK or DEK in the keychain directly. T3: any tamper with the AAD timestamps breaks the GCM tag, so deadline extension is cryptographically refused, not just policy-refused. Sliding refresh rewrites the record (new nonce, advanced idle deadline capped at the absolute deadline) via the atomic secure write helper.

**Option iii — opaque on-disk handle pointing at a keychain-held key.** The keychain holds the KEK or DEK itself (as the passkey-custody ADR's original cache sketched); the on-disk handle carries only entry name + deadlines. T1: safe. T2: same as ii. Weakness vs ii: the keychain entry alone IS the key — a leaked credential-store backup or a keychain-scoped attacker recovers usable key material without touching the disk record, and deadline enforcement is policy-only (nothing cryptographically binds the deadlines to the key). Also stores long-lived key material (the real DEK/KEK) in a surface designed for secrets-at-rest but outside the app's encrypted substrate custody.

**Evidence-favored: option ii.** It is the only candidate that (a) delivers login-once on BOTH backends, (b) keeps every on-disk byte ciphertext, (c) requires two independent artefacts (keychain entry + disk record) to reconstruct the DEK, and (d) makes expiry tamper-evident. It also lands the already-accepted passkey-custody "OS-keystore session cache" in a strictly stronger construction. Degenerate host without a usable OS keychain (headless Linux without Secret Service, `fail.Keyring`/`null.Keyring` probes at `_master_key.py:214`): no secure home for SK exists, so no persisted session is minted — the CLI falls back to per-process passphrase (interactive) or `CADRUMO_SECRET_PASSPHRASE` (CI), stated honestly at login. The ADR must decide this fail-closed degradation explicitly.

### Not investigated

- OS-native TPM/DPAPI-NG time-bound sealing (would harden T2 slightly but is per-OS bespoke work; the `keyring` adapter is the accepted portability boundary).
- Full DEK rotation on logout (rotation primitives exist at `adapters/persistence/storage/_rotation.py` but rotation is out of scope per the passkey-custody ADR's decision 6).
- Multi-profile concurrent sessions (single active pointer implies single active session; not a requirement).

## Sources

- `src/cadrumo/adapters/persistence/storage/master_key/_bucket_session.py:51,191,197,259`
- `src/cadrumo/adapters/persistence/storage/master_key/_active_session.py:48,97,146,178`
- `src/cadrumo/adapters/persistence/storage/master_key/_idle_timeout.py:31,43`
- `src/cadrumo/adapters/persistence/storage/master_key/_master_key.py:110,116,214,244,427,586,794`
- `src/cadrumo/adapters/persistence/storage/master_key/_master_key_derivation.py:12`
- `src/cadrumo/adapters/persistence/storage/master_key/_master_key_bucket_dek.py:27,49,64`
- `src/cadrumo/adapters/persistence/storage/sql/secure_objects.py:217`
- `src/cadrumo/core/_bucket_pointer_io.py:145`
- `src/cadrumo/core/config.py:574,985`
- `src/cadrumo/core/_config_storage_route.py:102`
- `src/cadrumo/application/user_profile/_orchestration.py:302,477`
- `src/cadrumo/application/user_profile/_profile_pointer_transaction.py:115`
- `src/cadrumo/application/auth/_sessions.py:171`
- `src/cadrumo/application/auth/_operator.py:756`
- `src/cadrumo/adapters/outbound/aeat/auth/_clave_movil.py:295`
- `src/cadrumo/entrypoints/cli/__init__.py:294,396`
- `src/cadrumo/entrypoints/cli/_config/_custody.py:109`
- `src/cadrumo/entrypoints/cli/_config/_auth.py:255,302`
- https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- https://pages.nist.gov/800-63-3-Implementation-Resources/63B/Session/
- https://pages.nist.gov/800-63-4/sp800-63b.html
- https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- https://support.1password.com/unlock-auto-lock/
- https://github.com/keepassxreboot/keepassxc/pull/12689
- https://bitwarden.com/help/vault-timeout/
- Unverified general-knowledge claim: none — every timing figure above is web-cited; Bitwarden's per-client default varies by client and is cited as approximate.
