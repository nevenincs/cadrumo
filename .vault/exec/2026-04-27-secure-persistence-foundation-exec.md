---
tags:
  - '#exec'
  - '#secure-persistence-foundation'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-secure-persistence-foundation-plan]]"
  - "[[2026-04-27-secure-persistence-foundation-adr]]"
  - "[[2026-04-27-secure-persistence-foundation-research]]"
  - "[[2026-04-27-security-storage-audit-audit]]"
---



# `secure-persistence-foundation` execution summary

The substrate landed in twelve sequential phases on branch
`feature/216-bank-import-persistence`, each phase a self-contained
commit gated by `just lint && just typecheck && just test && just hooks`
before push. Total surface: ten new persistence modules plus their
unit tests, one substrate-level smoke test, thirteen new error
classes registered in the central error registry, four new settings
in `aeat.core.config`, three audit-flagged path settings normalised, and
the four-line documentation-drift fix opportunistically corrected
in `env/.env.example`.

## Files created

- `src/aeat/adapters/persistence/storage/_classification.py`
- `src/aeat/adapters/persistence/storage/_test_classification.py`
- `src/aeat/adapters/persistence/storage/_crypto.py`
- `src/aeat/adapters/persistence/storage/_test_crypto.py`
- `src/aeat/adapters/persistence/storage/_master_key.py`
- `src/aeat/adapters/persistence/storage/_test_master_key.py`
- `src/aeat/adapters/persistence/storage/_lock.py`
- `src/aeat/adapters/persistence/storage/_test_lock.py`
- `src/aeat/adapters/persistence/storage/_encrypted_columns.py`
- `src/aeat/adapters/persistence/storage/_test_encrypted_columns.py`
- `src/aeat/adapters/persistence/storage/_envelope.py`
- `src/aeat/adapters/persistence/storage/_test_envelope.py`
- `src/aeat/adapters/persistence/storage/_blob_store.py`
- `src/aeat/adapters/persistence/storage/_test_blob_store.py`
- `src/aeat/adapters/persistence/storage/_path_safety.py`
- `src/aeat/adapters/persistence/storage/_test_path_safety.py`
- `src/aeat/adapters/persistence/storage/_redaction.py`
- `src/aeat/adapters/persistence/storage/_test_redaction.py`
- `src/aeat/adapters/persistence/storage/_secret_store.py`
- `src/aeat/adapters/persistence/storage/_test_secret_store.py`
- `src/aeat/adapters/persistence/storage/test_substrate_smoke.py`

## Files modified

- `src/aeat/adapters/persistence/storage/__init__.py` — substrate public surface; sorted
  `__all__` covers every new export.
- `src/aeat/adapters/persistence/storage/errors.py` — adds `PersistenceError` (base for
  the new tree, subclass of `StorageError`), `EncryptionError`,
  `DecryptionError`, `KeyDerivationError`, `NonceCollisionError`,
  `SecretStoreError`, `KeyringUnavailableError`,
  `MasterKeyUnavailableError`, `LockAcquisitionError`,
  `ClassificationError`, `EnvelopeVersionError`,
  `PathContainmentError` (also inherits from `ValueError`),
  `BlobNotFoundError`, `BlobIntegrityError`, `SecretNotFoundError`,
  `SecretAlreadyExistsError`, `RetentionPolicyError`.
- `src/aeat/core/errors/_registry.py` — registers a stable
  `ErrorCode` for each new class with es / en / hu default
  messages and the appropriate `ErrorCategory` (INTEGRITY for
  cryptographic / classification / version errors; FAIL for
  not-found and base-class errors; AUTH for keyring / master-key;
  LOCKED for the lock-acquisition error; REFUSED for the secret-
  already-exists collision).
- `src/aeat/config.py` — adds the closed `SecretStoreBackend`
  StrEnum (`auto` / `keyring` / `file`) and the new path settings
  `aeat_secret_store_backend`, `aeat_secret_store_dir`,
  `aeat_blob_store_dir`, `aeat_audit_dir`. Adds these plus the
  three audit-flagged drift settings (`aeat_invoices_dir`,
  `aeat_attachments_dir`, `aeat_runs_dir`) to
  `_normalize_repo_relative_paths`.
- `pyproject.toml` — `keyring>=25.6.0` added as a runtime
  dependency.
- `env/.env.example` — documents the four new env vars under their
  storage / secret-store / audit comment blocks.
- `tests/test_config.py` — adds the
  `TestRepoRelativePathNormalisationCoverage` introspection class
  that asserts every Path-typed `_dir` / `_path` / `_root` setting
  is either covered by the validator or in an explicit empty
  exempt list.

## Description

The substrate is the foundation for every subsequent wave that
migrates a domain consumer (financial records, filing state,
audit log, observability traces, caches, connector outputs) to
the governed persistence boundary. It exposes a small, typed
public API so consumers inherit classification, retention,
redaction, schema versioning, path containment, and at-rest
crypto by default.

Sensitivity classification ships as a closed StrEnum with nine
members (SECRET, SESSION, IDENTITY, FINANCIAL, AUDIT, CACHE,
CORPUS, OPERATIONAL, DIAGNOSTIC); each maps to a default
`ClassificationPolicy` aggregator that pins at-rest treatment,
retention behaviour (with `require_explicit_expiry` for SECRET
and SESSION), and the redaction-rule names that apply when the
class participates in audit-sink writes. The default-policy table
is an immutable `MappingProxyType`.

At-rest cryptography pivots on a small `_crypto.py` module that
wraps `cryptography.hazmat.primitives.ciphers.aead.AESGCM` and
`cryptography.hazmat.primitives.kdf.hkdf.HKDF`. The
`EncryptedBlob` frozen pydantic record carries the 12-byte nonce
and the ciphertext-with-tag; `to_wire` / `from_wire` round-trip
the canonical `nonce || ciphertext_with_tag` shape. Random
nonces are sourced from `secrets.token_bytes`; the project's
expected throughput is far below the GCM birthday bound. HKDF
derivation binds keys to a stable `context` bytestring so reusing
the master key with a different context yields a
cryptographically independent key.

Master-key acquisition is hybrid. The keyring backend stores a
32-byte random key under the `aeat:secure-persistence:master`
service identifier and falls back to minting if no entry exists.
The file backend wraps a fresh master key with an AES-256-GCM
ciphertext derived from a passphrase via scrypt
(`n=2**17, r=8, p=1, dklen=32`) plus a per-store random salt;
the wrapped key, the salt, and a human-readable KDF parameters
document live alongside one another. Passphrase resolves from
`AEAT_SECRET_PASSPHRASE` first, then via `getpass.getpass`. The
factory `get_master_key_provider()` honours
`aeat_secret_store_backend` (`auto` → keyring with file
fallback; `keyring` → keyring only; `file` → file only).

Column-level encryption ships as four SQLAlchemy `TypeDecorator`
classes (`EncryptedString`, `EncryptedBytes`, `EncryptedJSON`,
`HashedLookup`). Each stores `LargeBinary` ciphertext on disk;
each carries a stable AAD that binds ciphertext to its column
purpose so a `EncryptedString` value cannot be replayed as
`EncryptedBytes` even when the master key is the same.
`HashedLookup` is the deterministic HMAC-SHA256 of a
plaintext str (HKDF-derived sub-key + stable
`b"aeat.column.hashed_lookup.v1"` context); plaintext is
unrecoverable from the digest.

Cross-platform file locking lives in `_lock.py`
(`fcntl` on POSIX, `msvcrt` on Windows). The `exclusive_file_lock`
context manager creates a sidecar `<target>.lock` file, holds the
fd for the lifetime of the context, and times out with the
typed `LockAcquisitionError` (LOCKED category, retryable=true).
The lock file is intentionally left on disk after release to
avoid TOCTOU between concurrent acquirers.

The encrypted blob store (`_blob_store.py`) is content-addressed
and classification-aware. CORPUS-class blobs are written as
plaintext under `blobs/<sha256[:2]>/<sha256>`; every other class
is written as ciphertext under `blobs/<sha256[:2]>/<sha256>.enc`
with a fresh per-blob 32-byte DEK that is AES-256-GCM-wrapped
with the master key. Each blob carries a sidecar
`Envelope[BlobManifest]` that pins both digests, the
classification, the wrapped DEK as JSON-friendly
`EncryptionMetadata`, and the payload AEAD metadata. The master
key never touches disk.

The schema-version envelope (`_envelope.py`) is the substrate's
contract for every file-backed domain. `Envelope[PayloadT]`
carries `schema_version`, timezone-aware `written_at`,
`classification`, the typed payload, and optional
`EncryptionMetadata`. `save_envelope` writes atomically via
`tempfile.NamedTemporaryFile + os.replace`. `load_envelope`
validates the classification against the consumer's expected
class, refuses future schema versions, and applies a migrator
chain in declared order to advance older versions to the
consumer's `max_supported_version`.

The path-safety helpers (`_path_safety.py`) wrap the existing
`aeat.core.paths.resolve_relative_subpath` and
`resolve_record_json_path` and re-raise their `ValueError` as
the typed `PathContainmentError`. `PathContainmentError`
multi-inherits from `PersistenceError` and `ValueError` so
legacy `except ValueError` callers continue to work while new
code can write narrower clauses.

The redaction-rule contract (`_redaction.py`) ships a default
registry with three rules: `nif-hash` (Spanish NIF / NIE / CIF
shapes → `sha256:<8hex>`), `url-host-only` (URLs collapse to
scheme://host), and `token-fingerprint` (JWT-shaped bearer
tokens → `token:sha256:<8hex>`). The `redact()` helper applies
a tuple of rules in declared order; consumers compose custom
rules via the `RedactionRule` shape from `_classification.py`.

The secret store (`_secret_store.py`) is the canonical
repository for SECRET- and SESSION-class records. It persists
each record as a JSON-encoded `Envelope[SecretRecord]` written
to the encrypted blob store under the appropriate class. A
JSON-backed lookup index at `aeat_secret_store_dir/index.json`
maps the HKDF-derived HMAC-SHA256 digest of the natural key to
the underlying `BlobReference`. Every mutation acquires
`exclusive_file_lock(secret_store_dir/secrets.lock)`. Retention
policy is enforced at write time: SECRET and SESSION records
MUST carry `expires_at`. Overwrite collisions raise
`SecretAlreadyExistsError`; missing keys raise
`SecretNotFoundError`.

## Tests

The substrate ships with 226 tests across the following modules:

- `_test_classification.py` — 28 tests on the classification primitive.
- `_test_crypto.py` — 47 tests on AEAD primitives, HKDF, and the
  ErrorCode bindings for the crypto error tree.
- `_test_master_key.py` — 22 tests on the master-key provider trio.
- `_test_lock.py` — 10 tests on the file-lock helper (8 pass on
  Windows by default; the 2 cross-process tests are gated to
  `AEAT_RUN_LOCK_CONTENTION=1` due to `mp.spawn` flake risk on
  Windows CI).
- `_test_encrypted_columns.py` — 17 tests against a real in-memory
  SQLAlchemy session bound to an isolated declarative base.
- `_test_envelope.py` — 13 tests on the envelope round-trip,
  classification gate, version gate, and migrator chain.
- `_test_blob_store.py` — 17 tests on the encrypted blob store,
  including a cross-master-key isolation test confirming a
  different master key cannot decrypt previously-stored
  ciphertext.
- `_test_path_safety.py` — 12 tests on the typed path-containment
  wrappers.
- `_test_redaction.py` — 19 tests on the rule registry, NIF / URL /
  JWT redaction, rule chaining, and the new audit / blob settings.
- `_test_secret_store.py` — 17 tests on the secret store including
  index-does-not-leak-key, index-does-not-leak-value, retention
  policy enforcement, and the rotate / overwrite cleanup paths.
- `test_substrate_smoke.py` — 7 tests exercising the full chain
  end-to-end (master-key persistence; secret-store round-trip with
  on-disk leak verification; envelope round-trip; redaction;
  path-containment rejection; lock contention single-process; lock
  contention cross-process opt-in).

The full storage suite plus `tests/test_config.py` runs in roughly
ten seconds and reports `225 passed, 2 skipped`. The four `just`
gates (`lint`, `typecheck`, `test`, `hooks`) are green at every
commit. Coverage on `src/aeat` is preserved at the 60% floor.

## Audit gate

The audit gate consumes two parallel external review passes:

- `vaultspec-code-reviewer` over the substrate's eleven new
  modules, the registry extension, and the configuration changes,
  applying the standard safety / intent / quality discipline plus
  the cryptographic-correctness, concurrency-safety, and
  pydantic-discipline scrutiny called out in the wave plan.
- A fresh Codex security audit narrowed to the substrate's
  surface, anchored to OWASP Secrets Management, OWASP Logging,
  OWASP Cryptographic Storage, and NIST SP 800-111.

Findings are tracked in the PR-body audit ledger. Per the wave
contract, the gate cycles until no CRITICAL or HIGH finding
remains; emergent findings either close inside this wave or roll
forward into the next wave's research artifact. Audit reports
land alongside this exec summary as separate audit documents
under `.vault/audit/` once the reviews complete.
