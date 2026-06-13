---
tags:
  - "#research"
  - "#profile-lifecycle-disaster"
date: "2026-05-19"
modified: '2026-05-19'
related:
  - "[[2026-05-19-operator-blind-newcomer-testimony-audit]]"
  - "[[2026-05-19-operator-blind-returning-testimony-audit]]"
  - "[[2026-05-19-operator-blind-dual-testimony-audit]]"
  - "[[2026-05-19-operator-blind-fumbler-testimony-audit]]"
  - "[[2026-05-19-operator-testimonial-audit]]"
---

# profile-lifecycle-disaster research: axis A

Research axis A for the profile-lifecycle-disaster recovery campaign. Maps the exact
code path that must carry activate_session(BucketSession.open(...)) but does not
today, compares production-grade CLI lifecycle patterns, and recommends the minimal
architectural change that resolves Defect A (cold-start NoActiveBucketSessionError)
without introducing shims or parallel chains.
## Boot sequence today

The call graph from uv run aeat verb to the first column-level encrypt/decrypt
operation, as it exists on the chore/eliminate-shims branch.

Step 1: console_scripts["aeat"] invokes entrypoints/cli/__init__.py:main() (line 247).
Step 2: main() calls app(prog_name="aeat") (line 251).
Step 3: Typer dispatches @app.callback() to _root(ctx, ...) (line 84).
Step 4: _root() captures flags, calls apply_to_root_logger(), stores the format in
ctx.obj (lines 128-130). NO session is opened here. activate_session is not imported.
get_master_key_provider() is not called. BucketSession.open() is not called.
Step 5: Typer dispatches the subcommand verb (e.g. config profile create).
Step 6: The verb handler in entrypoints/cli/_config/__init__.py calls
build_lifecycle_service(bucket_id=pointer.bucket_id).
Step 7: The lifecycle service calls repository.save(profile_record).
Step 8: The repository persists via SQLAlchemy ORM with EncryptedString/EncryptedJSON
columns declared in the model.
Step 9: SQLAlchemy calls EncryptedString.process_bind_param(value, dialect) at
adapters/persistence/storage/crypto/_encrypted_columns.py line 110.
Step 10: process_bind_param() calls _resolve_master_key() (line 74).
Step 11: _resolve_master_key() delegates to get_active_master_key() (line 91).
Step 12: get_active_master_key() at _active_session.py lines 91-98 reads the
_active_session ContextVar, gets None, and raises NoActiveBucketSessionError.

The gap is between steps 4 and 5. No production code ever calls activate_session.
The _active_session ContextVar is always None when any ORM persist or load executes.

### Where activate_session exists today

activate_session is entered only from test-only code:

- adapters/persistence/storage/master_key/_master_key.py lines 838-851:
  EphemeralMasterKeyProvider.__enter__ — test fixtures only.
- adapters/persistence/storage/master_key/_master_key.py lines 894-915:
  UnsecuredMasterKeyProvider.__enter__ — implemented but never called in production
  (get_master_key_provider() returns a bare instance; no caller enters it as a
  context manager).

The activate_session contextmanager at _active_session.py lines 53-73 has zero
production callers. Its module docstring (line 14) states the CLI entry point
opens a session and enters activate_session — aspirational documentation that never
landed. No file under entrypoints/ or application/ imports activate_session.
The public re-export in adapters/persistence/storage/__init__.py (lines 142, 248)
is unreachable from production call paths.
## Where the session activation must happen

### Exact code location

entrypoints/cli/__init__.py, inside the _root callback body, after line 130
(state["format"] assignment) and before the if version: block. The Typer idiom
for a resource that lives for the verb duration is ctx.with_resource(...). The
activate_session contextmanager already satisfies contextlib.AbstractContextManager.

For UNSECURED mode the fix is a single line in the root callback:
    provider = get_master_key_provider()
    ctx.with_resource(provider)  # UnsecuredMasterKeyProvider.__enter__ already works

For KEYRING, FILE, and AUTO modes, those providers need __enter__ / __exit__ added
on the same pattern as UnsecuredMasterKeyProvider (lines 894-915 of _master_key.py).

### The two-tier session model required for cold start

A circular dependency prevents the root callback from always opening a session:
  - Session open requires bucket_id.
  - bucket_id requires an active profile pointer.
  - Active profile pointer is written by profile create.
  - profile create calls repository.save(), which requires a live session.

Resolution — two-tier model:

Tier 1 — root-callback session: opened when resolve_active_bucket_id() returns a
non-None value. Covers all operational verbs (app overview, app ledger, config
profile show, config profile switch, and all app sub-verbs).

Tier 2 — create-time transient session: opened inside profile create for the new
bucket, before the first encrypted write. The root callback skips the session open
when no active profile pointer exists. After profile create writes the manifest and
sets the pointer, subsequent invocations use tier 1.

Verbs with no encrypted dependency (--version, --help, profile list via manifest
scan) run without a session and must not trigger a session open.
## Comparable-CLI patterns

### GitHub CLI (gh) version 2.x

Cold start: gh auth status exits 1 with a clean message naming the remediation verb
(gh auth login). Tokens stored in OS keychain or 0600 file. No per-command session
object; credentials read at invocation time. No in-memory key zeroise on exit.

Relevance: applicable for the KEYRING pattern (read per invocation, no prompt if
keychain entry exists); not applicable for in-memory key material requiring
zeroise-on-exit.

### Bitwarden CLI (bw) version 2024.x

bw unlock derives a session key from the passphrase and emits it as the BW_SESSION
env var. Operator exports it. Every subsequent bw call reads BW_SESSION, uses it to
decrypt the local vault. bw lock ends the session.
Cold start without BW_SESSION: exits 1 with
"You are not logged in. Please log in and then unlock your vault."

Relevance: clean cold-start error plus explicit unlock verb is directly applicable.
aeat config profile switch NAME is the intended AEAT equivalent of bw unlock.
Today profile switch also raises NoActiveBucketSessionError because the handler
writes the pointer but never calls activate_session.

### 1Password CLI (op) version 2.x — strongest comparator

op signin authenticates and stores a session token in the OS keychain or via
OP_SESSION_<account> env var. Per-command: validates token expiry. Sessions expire
after 30 minutes of inactivity by default. Cold start: structured error plus
"Run op signin and try again." Lock: op signout or TTL expiry.

Relevance: strongest comparator. The 30-minute idle timeout exactly matches
BucketSession.is_expired() at _bucket_session.py lines 151-156. BucketSession has
the timeout mechanism but nothing checks it at verb entry. The signin / signout
lifecycle maps exactly to profile switch (open session) and profile logout
(clear pointer and close session).

### Borg Backup version 1.2.x / 2.x

BORG_PASSPHRASE env var or interactive prompt on every invocation. Per-command
passphrase resolution via Argon2 KDF. No session token survives across processes.

Relevance: AEAT FILE mode already implements this pattern inside
FileFallbackMasterKeyProvider.get_master_key(). The missing piece is not the KDF
derivation but the activate_session wrapper that carries the derived key into the
_active_session ContextVar.

### Restic version 0.16.x

RESTIC_PASSWORD env var, --password-file, or interactive prompt on every invocation.
No persistent session state. Process exit frees key material.

Relevance: on non-TTY without RESTIC_PASSWORD, emits a clean error rather than
blocking on getpass(). Directly applicable to AEAT FILE mode: if
AEAT_SECRET_PASSPHRASE is not set and stdin is not a TTY, emit a clean locale-keyed
operator error instead of hanging.

### gcloud CLI (Application Default Credentials)

gcloud auth login runs an OAuth2 browser flow and writes ADC credentials to disk.
Per-command: reads ADC file, refreshes OAuth token if expired.
Cold start: structured error plus remediation command. Less applicable (no local
at-rest encryption). The structured cold-start error pattern is universal.
## Per-backend cold-start contract

| Backend | Cold-start behaviour today | Cold-start behaviour proposed |
|---|---|---|
| AUTO | Provider constructed but never entered as context manager. First ORM op raises NoActiveBucketSessionError. | Root callback enters provider via ctx.with_resource(provider). __enter__ tries keychain; falls back to file on KeyringUnavailableError. Silent on keychain success; one passphrase prompt on file path. |
| KEYRING | Same failure. Keychain probed in constructor; instance returned but never entered. | Root callback enters provider. __enter__ calls get_master_key() silently (no prompt if keychain entry exists). On MasterKeyKeychainLockedError: clean locale-keyed operator error. |
| FILE | Same failure. Passphrase callback registered but get_master_key() never called before first ORM op. | Root callback enters provider. __enter__ reads AEAT_SECRET_PASSPHRASE or prompts via getpass if TTY. On non-TTY without env var: clean locale-keyed operator error. |
| UNSECURED | UnsecuredMasterKeyProvider.__enter__ implemented (lines 894-915 of _master_key.py) but never called in production. First ORM op raises NoActiveBucketSessionError. | Root callback calls ctx.with_resource(provider). __enter__ already works. No prompt. Requires AEAT_ALLOW_UNENCRYPTED=1. |

UNSECURED is the only backend where the fix is a single line in the root callback.
AUTO, KEYRING, and FILE require __enter__ / __exit__ to be added to their provider
classes.

### Bootstrap-exempt verb set

Verbs that must run without a root-callback session:
- profile create — opens its own transient session for the new bucket
- profile import — same; imported bundle decrypted at the source bucket
- config repair reset-state — must not require the session it is designed to clear
- --version, --help — no encrypted dependency
- profile list — reads manifest-scan computed mapping; no encrypted rows

All other verbs receive a session from the root callback and must emit a clean
locale-keyed no_active_profile operator error if no profile pointer exists, rather
than propagating a NoActiveBucketSessionError traceback.
## EphemeralMasterKeyProvider promotion

### Recommendation: promote the pattern, not the class

EphemeralMasterKeyProvider must remain test-only for three reasons:

Reason 1 — No stable bucket_id: __enter__ hardcodes bucket_id="ephemeral" (line 830
of _master_key.py). Production sessions need the real profile bucket_id for
BucketSession._evict_engine() to compute the correct SQLite URL at close time.
Using "ephemeral" would evict the wrong engine handle.

Reason 2 — No on-disk artefacts: the ephemeral key is randomly minted on
construction and never persisted. Every process restart loses all data encrypted
under it. Acceptable for test isolation; unacceptable for production.

Reason 3 — No factory registration: get_master_key_provider() has no SecretStoreBackend
value that maps to EphemeralMasterKeyProvider. Adding one would require a new enum
value and a hostile-named opt-out gate that serves no production purpose.

### What must change instead

Add __enter__ / __exit__ to KeyringMasterKeyProvider and FileFallbackMasterKeyProvider
following the pattern at UnsecuredMasterKeyProvider lines 894-915 of _master_key.py.
Each implementation must accept the real bucket_id from the caller.

Update UnsecuredMasterKeyProvider.__enter__ (line 904) to use the caller-supplied
bucket_id rather than the hardcoded "unsecured" string. A production unsecured
session with bucket_id="unsecured" would miss the real bucket engine on eviction.

Update get_master_key_provider() to accept an optional bucket_id: str | None
parameter. The root callback passes resolve_active_bucket_id(). When bucket_id is
None, the provider is constructed but the root callback skips ctx.with_resource.

EphemeralMasterKeyProvider retains its test-only role with bucket_id="ephemeral",
no SecretStoreBackend registration, and no production callers.
## Open questions for the ADR writer

1. Bootstrap exemption scope: which verbs are session-free? Minimum set is
   profile create, profile import, repair reset-state, --version, --help.
   Should profile census verbs (profile list, profile show when no session
   exists) also run session-free, or gate on an active profile pointer?

2. bucket_id at root-callback time: resolve_active_bucket_id() returns None when no
   pointer file exists. Should the root callback silently skip the session open
   and pass control to the subcommand, or immediately emit a clean operator error
   for all non-exempt verbs that need a session?

3. Passphrase prompt placement for FILE mode: should __enter__ prompt eagerly before
   subcommand dispatch, or defer until the first encrypted operation? Eager is
   cleaner for UX; deferred avoids prompting for session-free verbs called while
   a profile is active.

4. Idle-timeout enforcement: BucketSession.is_expired() is implemented but never
   checked. Should the ADR defer TTL enforcement to a future long-running mode, or
   specify the enforcement point now to prevent technical debt accumulation?

5. Passphrase cache elimination: _default_passphrase_callback reads
   AEAT_SECRET_PASSPHRASE or calls getpass once. With __enter__ / __exit__ managing
   session lifetime, does the in-process passphrase cache become redundant, or must
   it survive for potential future multi-verb interactive sessions?

6. repair reset-state session-free guarantee: the ADR must explicitly mark
   repair reset-state as session-free and confirm that the secure_objects table
   deletion uses raw DDL (DROP TABLE or DELETE FROM via text SQL) rather than
   ORM-mediated row deletion that would trigger column decryptors.

7. MasterKeyKeychainLockedError at root callback: on cancelled Windows Hello /
   macOS Touch ID, __enter__ raises MasterKeyKeychainLockedError. Should the global
   error boundary in entrypoints/cli/_errors.py handle this with a clean
   locale-keyed message, or should the exception propagate as a startup failure?
## Constraints inherited by the ADR writer

- No shims, no compatibility layers, no parallel chains: the old unwired flow
  (root callback does not open a session, column operations fail) must be replaced,
  not wrapped. Move every caller to the canonical path in the same commit.
- No deprecation paths: forward-only. The canonical path lands in full with no
  transition period where both old and new paths coexist.
- No destructive git operations in the shared worktree: fixes land as forward-only
  additive commits. No rebase, reset, stash, or checkout of paths.
- No naked English on the operator surface: every new cold-start error message
  requires a locale key added via python -m aeat.locales scaffold then audit.
  Bare string literals in operator-facing paths are forbidden.
- Locale changes go through the CLI: python -m aeat.locales scaffold then audit;
  hand-editing YAML locale structure is forbidden.
- Production config through Settings: no os.environ or os.getenv direct calls;
  use load_settings() or the Settings pydantic model.
- Pydantic v2 strict models at all persisted boundaries: no dict[str, Any] for
  any persisted record, wire payload, or configuration boundary.
- No tautological tests: session-lifecycle tests must exercise real cold-start
  behaviour with real SQLite and real providers (or EphemeralMasterKeyProvider for
  fixture cases); not mocked column decorators or patched ContextVar state.
- No live AEAT submission: the AEAT_LIVE_TESTS_ENABLED gate remains in force.
  Session-lifecycle work does not touch submission paths.
- UNSECURED mode requires AEAT_ALLOW_UNENCRYPTED=1: the refusal gate at
  get_master_key_provider() line 1053 of _master_key.py must remain. The
  auto-activate path for UNSECURED mode cannot silently bypass it.
