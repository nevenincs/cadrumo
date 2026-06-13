---
tags:
  - '#adr'
  - '#secure-persistence-foundation'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-secure-persistence-foundation-research]]"
  - "[[2026-04-27-security-storage-audit-audit]]"
  - "[[2026-04-12-data-storage-adr]]"
---



# `secure-persistence-foundation` adr: `secure-persistence-foundation-wave-1-adr` | (**status:** `accepted`)

## Problem Statement

The codebase has no governed persistence boundary. The 2026-04-27 security
storage audit grades the resulting state CRITICAL on two axes
(plaintext-on-disk credentials and session material; broad plaintext
business-record persistence with no classification model) and HIGH on
three more (the formal storage layer covers only three catalogue tables;
audit and debug artifacts persist sensitive context outside controlled
roots; profile and config CLI flows write identity directly to plaintext
files). The standing data-storage ADR adopted SQLite + SQLAlchemy +
Alembic for the centralised SQL surface but explicitly scoped the first
cut narrow; the audit asks for the expansion that ADR foreshadowed.

This ADR governs Wave 1 of the long-lived `secure-persistence-foundation`
feature. The wave delivers the substrate only — no domain consumer is
migrated. Subsequent waves consume the substrate and migrate domain by
domain. The substrate must give every future consumer safe-default
classification, retention, redaction, schema evolution, path containment,
and at-rest crypto without requiring any consumer to reinvent these
controls.

## Considerations

Architectural drivers:

- The standing data-storage ADR fixes SQLite + SQLAlchemy 2.x + Alembic
  for the SQL backend and mandates that callers import only from the
  public surface of the persistence subpackage. Both decisions are
  preserved here. The substrate generalises the existing
  `aeat.adapters.persistence.storage` public surface rather than introducing a new
  subpackage; the public name and import discipline remain stable.
- The standing pydantic-v2 mandate requires strict frozen models at
  every boundary. Every public record exposed by the substrate
  satisfies this. ORM rows remain internal.
- The project's error registry (post-#398) requires every public
  error class to carry a stable `ErrorCode` with es / en / hu default
  messages, a category, a retryable flag, and an optional runbook ID.
  The substrate registers a complete set up front so consumers in
  later waves can rely on stable codes.
- The CLI JSON-output schema registry (post-#399) governs machine-
  readable command output. The substrate does not add CLI commands in
  Wave 1; the secret-store CLI surface is deferred to Wave 2 with the
  canary consumer.
- The trilingual contract requires user-facing strings to be emitted
  via the Translatable pattern with `AEAT_OUTPUT_LANGUAGE` defaulting
  to `es`. New error messages and operator-facing summaries follow
  this contract. The data-storage ADR's `TODO(#20)` markers for
  translatable columns continue to apply to the new domain shapes.
- The project's testing mandate forbids mocks, fakes, stubs, freezegun,
  pytest-mock, and similar. Substrate tests use a real SQLAlchemy
  session against an in-memory SQLite database, real Fernet / AES-GCM
  primitives, real file-locking helpers, and real keychain backends
  where available (the keychain fallback path is exercised
  deterministically by injecting a backend that raises).
- Live AEAT submission remains permanently forbidden. The substrate
  has no surface that interacts with `live_submit_enabled`; the audit
  sink redesign is structural only.

Tech-stack considerations surveyed in the research artifact:

- Secret store mechanism: OS keychain via `keyring` only; encrypted-
  file fallback only; or hybrid. Hybrid retains keychain UX where
  available and degrades gracefully on CI / headless / disabled-
  keychain hosts. Hybrid is selected.
- At-rest crypto for SQL records: SQLCipher whole-database; column-
  level via SQLAlchemy `TypeDecorator`; or application-level envelope.
  Column-level is selected; SQLCipher is rejected on portability
  grounds (non-stdlib SQLite build, friction on Windows, lost
  per-column granularity); envelope is rejected because it gives up
  SQL search semantics on most fields.
- At-rest crypto for opaque blobs: per-blob envelope encryption with a
  master-key-wrapped DEK. Selected.
- Schema/version contract for file-backed domains: a small `Envelope`
  pydantic shape with `schema_version`, `written_at`, `classification`,
  `payload`, and optional `encryption` metadata. Selected.
- Cross-platform file locking: stdlib `fcntl` / `msvcrt` helpers vs
  `portalocker` or `filelock`. Stdlib is selected (no new
  dependency).
- Passphrase KDF: scrypt (already in `cryptography`) vs Argon2id
  (new dependency `argon2-cffi`). Scrypt selected for Wave 1 with
  parameters `n=2**17, r=8, p=1, dklen=32` and a per-store random
  salt. A future ADR may move to Argon2id once the dependency review
  approves it.
- AEAD primitive: AES-256-GCM via `cryptography.hazmat.primitives.ciphers.aead`.
  Twelve-byte random nonce per record, sixteen-byte tag, no
  associated-data tagging in v1 (associated data is reserved in the
  envelope schema for a future ADR).

## Constraints

- Python 3.13+, Windows-supported. Every primitive must work on
  Windows without a native compile step. `cryptography>=47.0.0` is
  already pinned; no further runtime dependencies are introduced for
  Wave 1.
- Existing `aeat.adapters.persistence.storage` public surface MUST remain importable for
  every existing caller (modelos, portals, corpus_artifacts). The
  substrate is additive at the public-surface level. The internal
  `_orm.py`, `engine.py`, `session.py`, `repository.py` modules grow
  but do not break callers.
- Path containment must remain at floor (path-handling audit
  established). The substrate adds containment to the three settings
  the security audit identified as drift-prone but does not regress
  any of the existing twenty-five.
- Schema migrations remain reviewable. Every Alembic revision shipped
  by Wave 1 round-trips via the existing `_test_migrations.py`
  pattern. Auto-apply on startup remains opt-in via
  `AEAT_STORAGE_AUTO_MIGRATE`.
- Coverage floor on `src/aeat` must stay at sixty percent.
- The branch `feature/216-bank-import-persistence` is the long-lived
  PR universe. No per-wave merges. Commits land in conventional-
  commits style; CI on the PR runs the four `just` gates plus
  Gemini's autonomous PR review.

## Implementation

The substrate is delivered as additions to the `aeat.adapters.persistence.storage`
subpackage. The public surface gains the following exports; the
underlying modules are organised into thematic clusters under
internal underscore-prefixed names. Every public symbol is documented
with a Google-style docstring; every record is strict frozen pydantic
v2.

### 1. Sensitivity classification primitive

A closed `enum.StrEnum` named `SensitivityClass` with members
`SECRET`, `SESSION`, `IDENTITY`, `FINANCIAL`, `AUDIT`, `CACHE`,
`CORPUS`, `OPERATIONAL`, `DIAGNOSTIC`. Every persisted record carries
its class. Default treatments are encoded in a `ClassificationPolicy`
pydantic record per class: at-rest treatment (`PLAINTEXT` |
`CIPHERTEXT_REQUIRED`), retention (a `RetentionPolicy` record with
`max_age` and `archive_after`), and a `RedactionRule` set used by the
audit sink and the run-trace path. The default policy table is
declared as a `MappingProxyType` in `aeat.adapters.persistence.storage._classification`
and exposed via `aeat.adapters.persistence.storage.default_policy_for(cls)`. Consumers MAY
override per-record but the default is always available.

### 2. Master-key acquisition

A `MasterKeyProvider` protocol with two concrete implementations:

- `KeyringMasterKeyProvider` — backed by the `keyring` package when
  importable and the platform default backend reports usable. The key
  identity is `aeat:secure-persistence-foundation:master`. The
  provider stores a 32-byte random key on first use and returns it
  on subsequent calls. The `keyring` import is lazy; the substrate
  does not introduce a hard runtime dependency.
- `FileFallbackMasterKeyProvider` — backed by an encrypted master-key
  file under the path `aeat_secret_store_dir / master.key` (the
  setting is added to `aeat.core.config` and is path-normalised). The
  master key is wrapped with a passphrase-derived KEK using scrypt
  (`n=2**17, r=8, p=1, dklen=32`) and a per-store sixteen-byte random
  salt persisted alongside. The passphrase is read from the
  environment variable `AEAT_SECRET_PASSPHRASE` when present, or
  prompted via `getpass.getpass` once per process and cached in
  memory for the process lifetime.

A factory `aeat.adapters.persistence.storage.get_master_key_provider()` returns the active
provider per the resolved `aeat_secret_store_backend` setting (closed
enum: `keyring` | `file` | `auto`; default `auto` selects keyring
when available and falls back to file). The provider is process-
singleton; tests inject a third `EphemeralMasterKeyProvider` that
generates a fresh random key per session.

`keyring` is added to `dependencies` as an optional install
(`pyproject.toml`'s `optional-dependencies.secure_persistence_foundation`).
The substrate functions correctly without `keyring` when the
selected backend is `file`. CI installs the optional group on the
Linux job; the keyring backend tests are guarded with
`pytest.importorskip("keyring")` and are skipped on platforms
without a usable backend.

### 3. AEAD primitives

A small `aeat.adapters.persistence.storage._crypto` module wraps `AESGCM` from
`cryptography.hazmat.primitives.ciphers.aead`. Public surface:

- `aeat.adapters.persistence.storage.encrypt_record(plaintext: bytes, *, key: bytes)
  -> EncryptedBlob` — generates a 12-byte random nonce, encrypts via
  AES-256-GCM, returns a frozen pydantic `EncryptedBlob` record with
  `nonce: bytes`, `ciphertext: bytes`, and `tag_present: bool`. The
  on-wire form is `nonce || ciphertext_with_tag`.
- `aeat.adapters.persistence.storage.decrypt_record(blob: EncryptedBlob, *, key: bytes)
  -> bytes` — decrypts and verifies the GCM tag; raises
  `EncryptionError` on tag mismatch.
- `aeat.adapters.persistence.storage.derive_key(*, key_material: bytes, salt: bytes,
  context: bytes) -> bytes` — HKDF-SHA256 derivation for per-row /
  per-blob keys.

Twelve-byte nonce uniqueness is guaranteed by sourcing nonces from
`secrets.token_bytes(12)`. The combinatorics are safe for the
project's expected throughput (the GCM birthday bound on a 96-bit
nonce permits roughly 2^32 random nonces per key; the project will
re-key well before that).

### 4. SQLAlchemy `TypeDecorator` set

`aeat.adapters.persistence.storage._encrypted_columns` exports `EncryptedString`,
`EncryptedBytes`, `EncryptedJSON`, and `HashedLookup`. Each
`TypeDecorator` performs encrypt-on-bind / decrypt-on-result via the
substrate's master key. Storage type is `BLOB` (not `VARCHAR`) so
ciphertext bytes round-trip cleanly across SQLite and a future
Postgres swap. `EncryptedJSON` round-trips through `json.dumps` /
`json.loads` with strict pydantic-mode-compatible serialisation.
`HashedLookup` is a deterministic HMAC-SHA256 hash of a natural key
keyed by a separate `lookup_key` derived from the master key plus a
fixed `context=b"aeat.lookup.v1"`; it gives consumers
search-by-equality without leaking the plaintext value.

### 5. Encrypted blob store

`aeat.adapters.persistence.storage._blob_store` provides an `EncryptedBlobStore` repository
with two layouts:

- Plaintext blobs (CORPUS class only) — written content-addressed
  under `aeat_blob_store_dir / blobs / <sha256[:2]> / <sha256>` with
  a sibling JSON manifest carrying `sha256`, `size`, `content_type`,
  `classification`, `written_at`. Existing financial-attachments
  semantics are preserved.
- Ciphertext blobs (every other class) — DEK is 32 random bytes,
  ciphertext is AES-256-GCM with a 12-byte nonce, the wrapped DEK
  uses AES-256-GCM keyed by the master key. The manifest carries
  `sha256_plaintext`, `sha256_ciphertext`, `wrapped_dek` (16 + 12
  bytes), `nonce`, `size`, `content_type`, `classification`,
  `written_at`.

The repository's public read API returns plaintext bytes; the
sensitivity class drives whether decryption is attempted. Manifests
are validated as pydantic v2 frozen records.

### 6. Schema-version envelope for file-backed domains

`aeat.adapters.persistence.storage._envelope` exports a generic `Envelope[PayloadT]`
pydantic v2 frozen model with fields `schema_version: int`,
`written_at: datetime` (timezone-aware), `classification:
SensitivityClass`, `payload: PayloadT | EncryptedBlob`, and
`encryption: EncryptionMetadata | None`. A small migrator helper
`load_envelope(path: Path, payload_type: type[PayloadT], *,
expected_class: SensitivityClass) -> Envelope[PayloadT]` reads the
file, verifies the classification matches, decrypts the payload when
encryption metadata is present, validates against `payload_type`,
and returns the typed envelope. A companion
`save_envelope(envelope: Envelope[PayloadT], path: Path) -> None`
writes atomically via the existing tempfile + `os.replace` pattern.

The envelope is the substrate's contract for file-backed domains.
Per-domain migrators (Wave 3 onward) implement
`migrate_envelope(envelope: Envelope, *, target_version: int)
-> Envelope` and the load helper applies migrators when the on-disk
version is older than the consumer's expected version. No-op for
Wave 1; the contract is in place.

### 7. Cross-platform file lock

`aeat.adapters.persistence.storage._lock` exports `exclusive_file_lock(path: Path, *,
timeout: float = 30.0)` as a context manager. POSIX uses
`fcntl.flock(fd, LOCK_EX | LOCK_NB)` with a sleep-and-retry loop
until timeout; Windows uses `msvcrt.locking(fd, LK_NBLCK, 1)` with
the same loop. The lock file is created adjacent to the protected
path (`<path>.lock`) and the lock fd is held for the duration of the
context. Timeout raises `LockAcquisitionError`. The helper is
internal (`_lock`) and consumers acquire locks via
`SecretStore.exclusive_lock()` or domain-specific repository
methods that document the lock semantics.

### 8. Path-normalisation fix

`aeat.core.config._normalize_repo_relative_paths` adds the three settings
the audit identified as drift-prone: `aeat_invoices_dir`,
`aeat_attachments_dir`, `aeat_runs_dir`. The new
`aeat_secret_store_dir`, `aeat_blob_store_dir`, and `aeat_audit_dir`
settings introduced by Wave 1 are also normalised. A regression test
asserts the validator covers every settings field whose name ends in
`_dir` or `_path`, and is parameterised against an explicit allow-list
of settings legitimately exempt from normalisation (e.g. URL-shaped
settings).

### 9. Secret store

`aeat.adapters.persistence.storage._secret_store` provides:

- `SecretRecord` (frozen pydantic v2): `key: str` (NFKC-normalised,
  case-sensitive, alphanumeric + `:` + `-` + `_`), `value: bytes`,
  `classification: SensitivityClass` (SECRET or SESSION),
  `metadata: dict[str, str]` (operator-supplied non-secret tags),
  `created_at: datetime`, `expires_at: datetime | None`.
- `SecretStore` repository: `put(record)`, `get(key) ->
  SecretRecord`, `delete(key)`, `list() -> list[str]`,
  `rotate(key, new_value)`. The store persists records via the
  encrypted blob store with ciphertext blob layout; the lookup
  index uses a separate SQLite table `secret_index` (key column is
  `HashedLookup`, payload column is the blob digest pointer).
- Concurrency: every mutation acquires
  `exclusive_file_lock(secret_store_dir / "secrets.lock")` for the
  call duration.

The store is consumed in Wave 2 by the secret-canary migrator. Wave 1
ships the API and exhaustive tests; no domain CLI surface lands here.

### 10. Audit sink contract

The substrate ships a `RedactionRule` pydantic-v2 frozen record and a
small `redact(value: object, *, rules: tuple[RedactionRule, ...])
-> object` helper that the audit sink uses at write time. Default
rules cover NIF / NIE shapes (regex-redacted to a SHA-256 prefix),
URL paths and query strings (host-only), bearer tokens and OAuth
authorisation headers (fingerprinted via SHA-256 prefix), and
process arguments (delegated to the existing run-trace
`cli/_observability.py` argument-redaction helpers, name-side-only).
The Wave-1 substrate exposes the rule set and the helper. Relocation
of `.aeat/live-submit-audit.log` and live-submit audit JSONL writers
is deferred to Wave 2 or Wave 4.

### 11. Error codes

The following error classes are added under `aeat.adapters.persistence.storage.errors`,
each registered in `aeat.core.errors._registry` at import time:

- `PersistenceError(StorageError)` — base for every new substrate
  error. `StorageError` remains the public name for the
  existing surface; `PersistenceError` is its subclass.
- `SecretStoreError(PersistenceError)` — base for secret-store I/O
  failures. Subclasses: `SecretNotFoundError`,
  `SecretAlreadyExistsError`, `KeyringUnavailableError`,
  `MasterKeyUnavailableError`.
- `EncryptionError(PersistenceError)` — base for AEAD failures.
  Subclasses: `DecryptionError`, `KeyDerivationError`,
  `NonceCollisionError` (defensive; the GCM birthday bound makes
  this practically unreachable).
- `RetentionPolicyError(PersistenceError)` — raised when a
  retention policy is violated at write time (e.g. attempting to
  write a SECRET-class record without an `expires_at`).
- `ClassificationError(PersistenceError)` — raised when a record's
  declared class is incompatible with its repository (e.g. a
  CORPUS-class blob written through the encrypted-blob path).
- `EnvelopeVersionError(PersistenceError)` — raised when an
  on-disk envelope is newer than the consumer's expected version
  and no forward migrator exists.
- `PathContainmentError(PersistenceError)` — raised when a
  computed path escapes its configured root.
- `LockAcquisitionError(PersistenceError)` — raised when an
  exclusive lock cannot be acquired within the timeout.

Each registration provides es / en / hu default messages, an
`ErrorCategory` (most are `INTEGRITY` or `FAIL`;
`LockAcquisitionError` is `LOCKED`; `KeyringUnavailableError` and
`MasterKeyUnavailableError` are `AUTH`), a `retryable` flag, and a
runbook ID (currently `null`; runbooks land in a separate doc
sweep). The CLI error decorator from #398 picks them up
automatically.

### 12. New settings

`aeat.core.config.Settings` adds the following fields (all path-normalised):

- `aeat_secret_store_dir: Path` (default `var/secrets`)
- `aeat_secret_store_backend: SecretStoreBackend` (closed enum:
  `keyring` | `file` | `auto`; default `auto`)
- `aeat_blob_store_dir: Path` (default `var/blobs`)
- `aeat_audit_dir: Path` (default `var/audit`)

Every new setting is documented in `env/.env.example` with the
trilingual comment pattern and the project's secret-marker
convention. The `LOW-MED` audit finding on `AEAT_LIVE_SUBMIT_ENABLED`
documentation drift is corrected opportunistically as part of the
example-file edit.

## Rationale

The architectural decisions above resolve the audit's CRITICAL and
HIGH findings as follows. Each finding maps to a structural change in
the substrate and a deliberate Wave-N migration target.

The audit's CRITICAL secret-persistence finding is structurally
addressed by the secret store (item 9). Migrating existing secret
files to the store is a Wave-2 activity; the substrate provides the
target. The keyring backend keeps OS-native confidentiality where
available; the file fallback keeps the substrate usable on CI and
headless hosts; the hybrid eliminates the binary platform-coupling
choice.

The audit's CRITICAL broad-plaintext business-record finding is
structurally addressed by the column-level encryption (item 4), the
encrypted blob store (item 5), and the envelope contract (item 6).
The classification primitive (item 1) gives every consumer a default
treatment without requiring it to invent the policy, and the policy
table is the single point of truth for retention and redaction.

The audit's HIGH narrow-storage finding is structurally addressed by
generalising the `aeat.adapters.persistence.storage` public surface. The data-storage ADR
intended this expansion; the audit is the prompt to deliver it. The
`StorageError` → `PersistenceError` subclass relationship preserves
the existing public name while adding the new sub-tree of error
codes.

The audit's HIGH unsafe-audit-persistence finding is partially
structurally addressed by the redaction rule contract (item 10) and
the `aeat_audit_dir` setting (item 12). Relocation is a Wave-2 or
Wave-4 activity; the substrate provides the target.

The audit's HIGH profile-and-config-CLI finding is structurally
addressed by the secret store (item 9) and is migrated in Wave 2
together with the secret canary.

The audit's MEDIUM-HIGH path-normalisation drift is fully resolved
in Wave 1 (item 8). The fix is mechanical and lands as a Phase-0
quick-win at the start of the wave's exec phase.

The audit's MEDIUM schema-evolution-fragmentation finding is
structurally addressed by the envelope contract (item 6). Per-
domain adoption in Waves 3..7.

The audit's MEDIUM connector-export finding is deferred to Wave 7
in full.

The audit's LOW-MED `AEAT_LIVE_SUBMIT_ENABLED` documentation drift
is opportunistically corrected when item 12 edits
`env/.env.example`.

## Consequences

Positive:

- Every future persistence consumer inherits classification,
  retention, redaction, schema versioning, path containment, and
  at-rest crypto by default. Implementers stop reinventing controls.
- The standing data-storage ADR's intent is restored. The narrow
  scope of the original three tables expands without breaking the
  public surface or the import discipline.
- The secret store is portable. CI and headless contexts work via
  the file backend; operator workstations get OS-keychain UX. The
  binary coupling that often blocks secrets work is eliminated.
- The schema-version envelope gives file-backed domains the same
  evolution discipline as Alembic-managed SQL records. Per-domain
  migrators are small and reviewable.
- Path normalisation drift is closed. The audit's MEDIUM-HIGH
  finding is exhausted within Wave 1.

Negative:

- The `cryptography` package is already a direct dependency, but
  Wave 1 adds `keyring` as an optional dependency. Operators who
  install the optional group get keyring; operators who do not get
  the file backend transparently. CI exercises both.
- Encrypted columns lose SQL search semantics on the encrypted
  fields. Consumers that need search-by-natural-key use the
  `HashedLookup` decorator (deterministic HMAC) and pay the cost
  of an extra column. This is documented in the substrate's
  developer guide and discoverable via the type's docstring.
- The substrate adds surface area to `aeat.adapters.persistence.storage`. The internal
  modules grow; the public surface gains roughly twenty new
  exports (sensitivity enum, classification policy, master key
  provider protocol and concretes, encrypt/decrypt helpers, four
  type decorators, blob store, envelope helpers, secret store,
  redaction primitives, and the new error classes). Downstream
  consumers rely on stability of these names; any rename requires
  an ADR amendment.

Neutral:

- No CLI surface lands in Wave 1. The secrets CLI lands in Wave 2.
- SQLCipher remains rejected for now. A later ADR may revisit if
  per-column granularity is no longer required and the portability
  cost is accepted.
- Argon2id remains a deferred upgrade. Wave 1 ships scrypt; a
  later ADR may swap it once `argon2-cffi` is approved.

The audit gate at the end of Wave 1 verifies every CRITICAL and HIGH
finding tagged "Wave 1 substrate" in the research artifact is
structurally addressed and that no new CRITICAL or HIGH finding is
introduced by the substrate's own implementation. Findings the gate
cannot close roll forward into Wave 2's research artifact.
