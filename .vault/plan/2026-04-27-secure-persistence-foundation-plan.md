---
tags:
  - '#plan'
  - '#secure-persistence-foundation'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-secure-persistence-foundation-adr]]"
  - "[[2026-04-27-secure-persistence-foundation-research]]"
  - "[[2026-04-27-security-storage-audit-audit]]"
---



# `secure-persistence-foundation` `secure-persistence-foundation-wave-1-plan` plan

This plan operationalises the Wave-1 ADR. The substrate ships in nine
phases. Phases land as discrete commits. The four `just` gates must
be green before each commit. Audit-gate at end of Wave 1 cycles until
no CRITICAL or HIGH finding remains; emergent findings either close in
Wave 1 or open Wave 2.

## Proposed Changes

Wave 1 lands the governed persistence boundary inside the existing
`aeat.adapters.persistence.storage` subpackage. No domain consumer is migrated; every
existing caller (`modelos`, `portals`, `corpus_artifacts`) continues
to work without modification. Public API additions are documented in
the ADR's Implementation section. The plan tracks the build order
(low-risk fixes first, primitives next, repositories last) and the
verification criteria at every phase boundary.

## Tasks

### Phase 0 — Path-normalisation quick-fix

1. Extend `_normalize_repo_relative_paths` in `src/aeat/config.py`
   to cover `aeat_invoices_dir`, `aeat_attachments_dir`, and
   `aeat_runs_dir`. Add a regression test that asserts every
   settings field whose name ends in `_dir` or `_path` is either
   in the validator list or in an explicit allow-list of legitimate
   exemptions (URL-shaped settings, settings holding absolute
   third-party paths). Update `env/.env.example` if needed; correct
   the `AEAT_LIVE_SUBMIT_ENABLED` documentation drift opportunistically.
2. Verification: `just lint && just typecheck && just test && just hooks`
   pass; the new regression test fails on a deliberately-omitted
   setting and passes once added.

### Phase 1 — Sensitivity classification primitive

1. Add `aeat/adapters/persistence/storage/_classification.py` with `SensitivityClass`
   `StrEnum`, `RetentionPolicy` and `RedactionRule` frozen pydantic
   v2 records, `ClassificationPolicy` aggregator, and the default
   policy table as `MappingProxyType`. Public exports added to
   `aeat/adapters/persistence/storage/__init__.py`.
2. Tests: every class member has a default policy; default policy
   is immutable at runtime; `default_policy_for` returns the
   expected record per class.
3. Verification: `just lint && just typecheck && just test && just hooks`.

### Phase 2 — AEAD primitives and HKDF

1. Add `aeat/adapters/persistence/storage/_crypto.py` with `EncryptedBlob` frozen
   pydantic record, `encrypt_record`, `decrypt_record`, and
   `derive_key`. Wraps `cryptography.hazmat.primitives.ciphers.aead.AESGCM`.
   Public exports added.
2. Add `aeat/adapters/persistence/storage/errors.py` extensions: `PersistenceError`,
   `EncryptionError`, `DecryptionError`, `KeyDerivationError`,
   `NonceCollisionError`. Each is registered in
   `aeat/core/errors/_registry.py` with es / en / hu default messages,
   the appropriate `ErrorCategory`, and `runbook_id=None`.
3. Tests: round-trip encrypt-then-decrypt for binary, ASCII, and
   unicode plaintext (Spanish accented characters); tag-mismatch
   raises `DecryptionError` with the registered code; HKDF
   derivation is deterministic for fixed inputs.
4. Verification: pass the four `just` gates.

### Phase 3 — Master-key provider

1. Add `aeat/adapters/persistence/storage/_master_key.py` with `MasterKeyProvider`
   protocol, `KeyringMasterKeyProvider` (lazy import of `keyring`),
   `FileFallbackMasterKeyProvider` (scrypt KDF + AES-GCM-wrapped
   master key file), and `EphemeralMasterKeyProvider` for tests.
   Add `SecretStoreBackend` `StrEnum` to `aeat/config.py` and the
   `aeat_secret_store_backend` setting (default `auto`).
2. Add `aeat_secret_store_dir` setting (default `var/secrets`),
   path-normalised. Document it in `env/.env.example`.
3. Add `aeat/adapters/persistence/storage/errors.py` extensions: `SecretStoreError`,
   `KeyringUnavailableError`, `MasterKeyUnavailableError`. Register
   error codes (categories `INTEGRITY` and `AUTH`).
4. Add `keyring` to `pyproject.toml` `optional-dependencies`
   under a new `secure_persistence_foundation` extra. Run
   `uv lock --upgrade`.
5. Tests: file-fallback round-trip (write then read returns same
   key bytes); passphrase from env var path; passphrase prompt
   path uses an injected stub for stdin; keyring path guarded by
   `pytest.importorskip("keyring")`; `auto` backend selects
   keyring when available, file otherwise.
6. Verification: pass the four `just` gates.

### Phase 4 — File-lock helper

1. Add `aeat/adapters/persistence/storage/_lock.py` with `exclusive_file_lock(path,
   timeout)` context manager. Stdlib only (`fcntl` on POSIX,
   `msvcrt` on Windows). Add `LockAcquisitionError` to errors and
   register the code (category `LOCKED`, retryable `True`).
2. Tests: lock acquired and released cleanly; second concurrent
   acquirer fails after timeout; lock file is cleaned up on
   exception. Use real subprocesses via `multiprocessing` to test
   contention without mocks.
3. Verification: pass the four `just` gates.

### Phase 5 — Encrypted column TypeDecorators

1. Add `aeat/adapters/persistence/storage/_encrypted_columns.py` with `EncryptedString`,
   `EncryptedBytes`, `EncryptedJSON`, `HashedLookup`. Each
   `TypeDecorator` consults the active master key provider via the
   process-singleton factory. Public exports added.
2. Tests: round-trip via a real in-memory SQLAlchemy session
   against a test mapper class with each decorator. Verify
   ciphertext bytes are stored (the column value, fetched via raw
   SQL, is not the plaintext). `HashedLookup` produces stable
   digests across sessions when the master key is stable.
3. Verification: pass the four `just` gates.

### Phase 6 — Encrypted blob store

1. Add `aeat/adapters/persistence/storage/_blob_store.py` with `EncryptedBlobStore`
   repository. Public records: `BlobManifest` (frozen pydantic v2)
   and `BlobReference`. Configuration via `aeat_blob_store_dir`
   (new setting, path-normalised, default `var/blobs`).
2. Layout: plaintext (`CORPUS` only) under `blobs/<sha256[:2]>/<sha256>`
   with sibling `<sha256>.manifest.json`; ciphertext (every other
   class) under `blobs/<sha256[:2]>/<sha256>.enc` with sibling
   `<sha256>.manifest.json` carrying the wrapped DEK. Manifests are
   `Envelope[BlobManifest]` instances written via the helper from
   Phase 7.
3. Add `ClassificationError` to errors and register the code.
4. Tests: write-and-read round-trip per class; CORPUS is plaintext
   on disk; non-CORPUS is ciphertext on disk; tampering with the
   ciphertext or wrapped DEK produces `DecryptionError`;
   write-classification mismatch produces `ClassificationError`.
5. Verification: pass the four `just` gates.

### Phase 7 — Schema-version envelope

1. Add `aeat/adapters/persistence/storage/_envelope.py` with generic `Envelope[PayloadT]`
   pydantic v2 frozen model, `EncryptionMetadata` frozen record,
   `load_envelope`, `save_envelope`, and a stub `migrate_envelope`
   protocol for future per-domain migrators (no concrete migrator in
   Wave 1).
2. Add `EnvelopeVersionError` to errors and register the code.
3. Tests: round-trip plaintext envelope; round-trip encrypted
   envelope; older-than-expected version with no migrator raises
   `EnvelopeVersionError`; tamper detection via the embedded
   `written_at` validation; classification-mismatch on load raises
   `ClassificationError`.
4. Verification: pass the four `just` gates.

### Phase 8 — Path containment helper expansion

1. Add `PathContainmentError` to errors and register the code.
2. Audit `aeat/_paths.py` — confirm every path-resolution helper
   raises `PathContainmentError` (or its registered alias) on
   traversal violation. Where the existing helper raises a bare
   `ValueError`, narrow to the registered error.
3. Tests: a deliberate `..` traversal raises the registered error;
   absolute-path escape raises the registered error; legitimate
   nested paths resolve cleanly. Use real path manipulation against
   a fresh `tempfile.TemporaryDirectory`.
4. Verification: pass the four `just` gates.

### Phase 9 — Secret store

1. Add `aeat/adapters/persistence/storage/_secret_store.py` with `SecretRecord` frozen
   pydantic v2 model, `SecretStore` repository (`put`, `get`,
   `delete`, `list`, `rotate`), and an SQLite-backed lookup index
   (`secret_index` table with `HashedLookup` PK and a digest pointer
   column). The store persists records via the encrypted blob store
   in ciphertext layout and acquires
   `exclusive_file_lock(secret_store_dir / "secrets.lock")` for
   every mutation.
2. Add `SecretNotFoundError` and `SecretAlreadyExistsError` to
   errors and register their codes.
3. Add Alembic revision for the `secret_index` table. Round-trip
   the migration via the existing `_test_migrations.py` pattern.
4. Add `RetentionPolicyError` to errors and register the code; the
   secret-store `put` method raises it when a `SECRET`-class record
   has no `expires_at`.
5. Tests: full lifecycle (put, get, list, rotate, delete); two
   concurrent `put` invocations on the same key serialise via the
   lock; round-trip survives master-key rotation when the file
   backend is in use; the lookup index gives stable equality
   queries; classification rules are enforced.
6. Verification: pass the four `just` gates.

### Phase 10 — Audit-sink redaction contract

1. Add `aeat/adapters/persistence/storage/_redaction.py` with `RedactionRule` frozen
   pydantic v2 record (regex pattern, replacement strategy:
   `SHA256_PREFIX` | `HOST_ONLY` | `FINGERPRINT` | `ELLIPSIS`),
   `redact(value, *, rules)` helper, and a default rule set as
   `MappingProxyType`. Default rules: NIF/NIE → SHA-256 prefix;
   URLs → host-only; bearer / OAuth tokens → fingerprint.
2. Add `aeat_audit_dir` setting (default `var/audit`),
   path-normalised. Document in `env/.env.example`.
3. Tests: every default rule produces stable, irreversible output
   for representative inputs; chained rules apply in order;
   non-matching inputs pass through unchanged.
4. Verification: pass the four `just` gates.

### Phase 11 — Public surface, docs, and substrate-level smoke

1. Update `aeat/adapters/persistence/storage/__init__.py` to export every new public
   symbol per the ADR. Sort `__all__` alphabetically.
2. Add a substrate-level smoke test that exercises the full chain
   end-to-end: master-key provider (file backend) → encrypted
   blob store → secret store put/get/delete → envelope round-trip
   → redaction → file-lock contention. The test is deliberately
   slow and runs in CI's full suite. Marker:
   `[pytest.mark.unit, pytest.mark.domain_local_state]`.
3. Verification: pass the four `just` gates; coverage floor 60% on
   `src/aeat` preserved (`just test-cov`).

### Phase 12 — Audit gate (Wave 1)

1. Run `vaultspec-code-review` over every file changed by Wave 1.
   Address every CRITICAL and HIGH finding before proceeding.
2. Run a fresh Codex security audit narrowed to Wave-1 surface
   (the new `aeat.adapters.persistence.storage` modules + `aeat.core.config` extensions +
   `aeat.core.errors._registry` extensions). Address every CRITICAL
   and HIGH finding before proceeding.
3. Update the PR description body with the Wave-1 summary, the
   gate's findings, and the Wave-2 entry-point research seed.
4. Push to GitHub for Gemini's autonomous PR review; address any
   CRITICAL or HIGH finding Gemini raises.
5. Cycle the gate until no CRITICAL or HIGH finding remains. Then
   open Wave 2's research artifact under the same feature tag.

## Parallelization

Phases 1, 2, and 4 are independent and can be implemented in any
order. Phase 3 depends on Phase 2 (master-key wrapping uses the AEAD
primitives). Phase 5 depends on Phase 3 (TypeDecorators consult the
master-key provider). Phase 6 depends on Phases 2, 3, and 7 (blob
manifests are envelopes). Phase 7 depends on Phase 2 (envelopes
optionally carry an `EncryptedBlob`). Phase 9 depends on Phases 4,
5, 6, and 7 (lock + encrypted columns + encrypted blob store +
envelope). Phase 10 is independent of Phases 5–9 and can run in
parallel with Phase 8.

The build order in this plan is sequential and conservative; an
agent free to parallelise can run Phases 0, 1, 2, 4, 8, 10 in any
order, then 3, then 5, 6, 7, then 9, then 11, then 12.

## Verification

Mission success for Wave 1 is structural, not consumer-driven. The
substrate is verified by:

- Every ADR Implementation item is shipped behind tests that exercise
  real I/O against `tmp_path` and a real in-memory SQLAlchemy
  session. No mocks, no fakes, no stubs, no freezegun, no
  pytest-mock, no time-machine, no vcr.
- Every new public symbol is documented with a Google-style
  docstring, has full type hints, and is exported from
  `aeat/adapters/persistence/storage/__init__.py` with a sorted `__all__` entry.
- Every new error class registers an `ErrorCode` row with es / en /
  hu default messages.
- The four `just` gates (`lint`, `typecheck`, `test`, `hooks`) are
  green at every commit. Coverage floor 60% on `src/aeat` preserved.
- The Wave-1 audit gate (Phase 12) closes every CRITICAL and HIGH
  finding tagged "Wave 1 substrate" in the research artifact and
  raises no new CRITICAL or HIGH finding against the substrate's own
  implementation. Findings the gate cannot close are recorded in the
  Wave-2 research artifact's open-finding inventory.
- The PR body is updated at the end of the wave with the wave
  summary, the gate's outcome, the audit-finding ledger (closed,
  rolled-forward, deferred), and the Wave-2 entry point.

The substrate has no end-user CLI surface. Visual confirmation by an
operator is not part of Wave-1 verification. Consumer-level
demonstrations land in Wave 2 (secret canary) and Wave 3 (financial
domain, including the original issue #216 Kent moment).

## Plan self-review

Self-reviewed against the project mandates and the user's standing
constraints:

- Pydantic v2 mandate: every new record (`SensitivityClass` enum,
  `RetentionPolicy`, `RedactionRule`, `ClassificationPolicy`,
  `EncryptedBlob`, `BlobManifest`, `BlobReference`,
  `EncryptionMetadata`, `Envelope`, `SecretRecord`,
  `SecretStoreBackend` enum) is frozen and strict. Confirmed.
- Public API discipline: callers continue to import only from
  `aeat.adapters.persistence.storage`. Internal modules remain underscore-prefixed.
  Confirmed.
- No mocks: every test uses real I/O against `tmp_path`, real
  in-memory SQLAlchemy session, real `cryptography` primitives,
  real `multiprocessing` for lock contention. Confirmed.
- Trilingual contract: every new error registers es / en / hu
  default messages. Operator-facing strings (none in Wave 1)
  follow the Translatable pattern. Confirmed.
- Live AEAT submission: substrate has no surface that interacts
  with `live_submit_enabled`. The redaction contract is structural
  only. Confirmed.
- Conventional commits: every commit follows
  `<type>(<scope>): <subject>` with the scope mapping to the
  affected subpackage cluster (`storage`, `config`, `errors`,
  `paths`). Confirmed.
- Branch hygiene: `feature/216-bank-import-persistence` is the
  long-lived universe. No per-wave merges. Per-phase commits push
  to the upstream branch for Gemini's autonomous PR review.
  Confirmed.
- Issue ledger: PR #216 stays open and serves as the rolling
  tracker. No new issues filed. Confirmed.
- ADR size policy: this plan stays well below the 500 KB cap; the
  ADR likewise. Confirmed.
- Cross-feature collisions: in-flight branches (#321 modelo-130,
  the held #432 live-submit-forbidden, #395 kind-registry,
  the merged #239 aeat-verify) own disjoint subpackages. Wave 1's
  surface (`aeat.adapters.persistence.storage`, `aeat.core.config`, `aeat.core.errors`,
  `aeat.core.paths`, `env/.env.example`) does not overlap with any of
  them. Confirmed.

The plan is approved for execution. The next vault artifact is the
`exec` record set under
`.vault/exec/2026-04-27-secure-persistence-foundation/`.
