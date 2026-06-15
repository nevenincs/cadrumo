---
tags:
  - '#research'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
related: []
---



# `storage-backend-security-review` research: `secure storage backend adversarial and structural audit`

A five-axis read-only discovery swarm audited the secure-storage backend for an
adversarial-security and structural review. Each axis grounded through the
vaultspec-rag service then confirmed with `rg` and direct reads, verifying every
finding against HEAD. The yardstick is the canonical
`2026-05-22-secure-storage-production-hardening-architecture-adr`, which already
mandates the runtime-wrapper / `StorageRuntime` boundary, the central namespace
registry, fail-closed listing, and revision lineage. This review measures the
residual gap against that architecture and adds a fresh security-first pass the
prior hardening campaign did not frame adversarially.

## Baseline (verified sound — do not re-do)

- Steady-state at-rest pipeline: AES-256-GCM (12-byte per-call nonce, 16-byte
  tag), Argon2id KEK at OWASP-2024 baseline, per-bucket DEK wrapped with AAD
  `aeat.dek-wrap.v1:{bucket_id}` (genuine cross-bucket-swap prevention).
- File-envelope AAD binds classification + per-consumer HKDF context; class gate
  runs before master-key consult.
- Sealed-archive layout/member-order validated before any decrypt; header
  `manifest_digest`+`bucket_id` bound into payload AAD.
- Strict-pydantic envelopes with `schema_version` everywhere; no `dict[str, Any]`
  at any storage persistence boundary; the eight `cast(...)` calls are documented
  TypeVar-erasure boundary casts.
- Runtime-wrapper enrollment is broad (40 production files); core financial
  aggregates persist correctly through the encrypted substrate.
- `save_many` is atomic (one `session_scope`); default listing is fail-closed;
  no stale-after-write data cache above the loader.

## Findings — HIGH

- **H1 security — export archive KDF.** `application/bucket_maintenance/_service.py`
  derives the recovery-passphrase export-archive sealing key with HKDF-SHA256 (no
  work factor) instead of a password KDF. An exported `.tar.gz` that leaves the
  host is offline brute-forceable at full hardware speed against a human-chosen
  passphrase. Fix: Argon2id (`derive_kek_with_params`) with a fresh per-archive
  salt; persist the Argon2 params in the recovery-wrap member. Keep HKDF only for
  the high-entropy mnemonic recovery-key path.
- **H2 security — decrypted PDF to /tmp.** `adapters/outbound/aeat/sede/_declarations_observations.py`
  (`_temporary_sensitive_pdf_path`, used ~:414) writes a decrypted filed
  declaration to a plaintext `/tmp` scratch file on the bbox-extraction branch
  because `pdfplumber.open` wants a path. Violates
  `sensitive-financial-data-secure-storage-only`. Fix: parse in memory via
  `io.BytesIO(body)` (the in-memory `parse_declaracion_bytes` path already exists);
  delete the tempfile helper. Conditional on `bbox_anchored` profiles (M130/M131).
- **H3 integrity — AEAD does not bind row identity; integrity columns unverified
  on read.** `crypto/_encrypted_columns.py` encrypts with a static column-type AAD
  only; `secure_objects.py` writes `payload_hash`/`ciphertext_hash`/`revision_id`
  but never recomputes/compares them on `load`/`list_records`. A ciphertext BLOB
  copied from row A into row B (same bucket) decrypts cleanly — row-substitution /
  stale-revision replay is undetectable to every consumer read. Corroborated
  independently by the crypto and correctness axes. Fix: bind
  `namespace || object_key_digest || schema_version` into the AEAD AAD, AND verify
  `sha256(payload) == payload_hash` + recomputed `revision_id` on read, failing
  closed. (Pre-beta, no released data, so the AAD scheme may change outright.)
- **H4 cross-machine — absolute `source_path` baked into persisted+exported
  records.** `domain/transactions/_raw_transaction.py` stores
  `RawProvenance.source_path: Path` with a `.resolve()` validator; it rides every
  `Transaction` into the encrypted catalogue and the v2 portable bundle. The
  validator re-runs `.resolve()` on rehydration, so a POSIX-authored bundle
  imported on Windows mutates `/home/alice/bank.csv` → `C:\home\alice\bank.csv` —
  breaks strict cross-OS roundtrip equality and leaks username/dir layout. Fix:
  persist a relative filename or `source_sha256`-only reference; never `.resolve()`
  into a persisted/serialised shape.
- **H5 concurrency — no `busy_timeout`/WAL; SQL writes take no bucket lock.**
  `sql/engine.py` sets only `foreign_keys=ON`. With rollback-journal +
  `busy_timeout=0`, two invocations on one profile collide with an immediate
  "database is locked". The bucket lockfile guards directory lifecycle, not row
  writes. Fix: `PRAGMA busy_timeout`, `journal_mode=WAL`, `synchronous=NORMAL` in
  the connect listener.
- **H6 correctness — cross-store rename label drift undetected.**
  `application/user_profile/_profile_repository.py` writes the encrypted record
  `display_name` then the plaintext manifest `label`; `verify_profile_integrity`
  compares only `bucket_id`/`profile_id`/`status`, never the label, though the
  docstring claims a torn rename raises `ProfileIntegrityError`. Fix: compare
  manifest label vs record `display_name` and raise on divergence (mirror the
  status pattern), or correct the docstring and route detection through `repair`.
- **H7 performance — whole-catalogue rewrite per single-row mutation.**
  `domain/transactions/_repository.py` persists the entire `TransactionCatalogue`
  as one encrypted BLOB; every add/update/classify/review decrypts+parses+
  re-encrypts the whole catalogue. `attach_evidence` (`application/ledger/_actions_manual.py`)
  decrypts it twice per call. Fix (tactical): thread one decrypted catalogue
  through each command (kill the double-decrypt). Fix (architectural): one
  secure-object row per transaction keyed by `transaction_id`.
- **H8 legacy — v1 portable-bundle compat branch.**
  `application/user_profile/_bundle.py` keeps `SUPPORTED_BUNDLE_SCHEMA_VERSIONS =
  {1, 2}` and an `if bundle_schema_version == 1: return` read-tolerance branch.
  `no-legacy-compatibility` (2026-06-10 operator directive) is newer than and
  supersedes the `2026-05-27-profile-portability-adr` clause "v1 bundles remain
  importable". ADJUDICATION: pre-beta, no released data, no writer emits v1 —
  delete the `== 1` branch and drop `1` from the supported set.
- **H9 standardisation — namespace-literal duplication; adoption gate blind
  outside `application/`.** `test_namespace_registry_adoption.py` scans only
  `src/aeat/application`, so `domain/` and `adapters/outbound/` repositories
  redeclare namespace strings that exactly duplicate
  `STORAGE_NAMESPACE_REGISTRY` definitions (invoices, transactions, submission,
  filing, calculation_revisions, llm cache/usage, sede observation stores, and a
  ~12-site tail). Violates `aeat-schema-central-config`. Fix: reference the
  registry constant's `.namespace`, and extend the adoption gate to `domain/` and
  `adapters/outbound/`.
- **H10 structure — `domain/fincas/_repository.py` hexagonal inversion.** A
  `domain/` repository imports `adapters...storage.sql._orm` and operates on raw
  SQLAlchemy `Session` + `FincaRow` (not re-exported anywhere); the other domain
  repos persist via `SecureBoundRepository`. Stale docstring path
  `...storage._orm`. Fix: façade a typed repository at the `sql`/storage-root
  surface or relocate the ORM-coupled repository into the persistence adapter.
- **H11 structure — private-submodule imports where a re-export exists.**
  `application/workflow/_profile_health.py` (×5) and `entrypoints/cli/_overview.py`
  (×1) dot into `bucket._layout`/`._manifest`/`._manifest_io` though all symbols
  are in `bucket.__all__`. Fix: import from the package surface
  (`service-imports-via-top-level-reexports`).

## Findings — MEDIUM

- **M1 contract — import never recomputes `manifest_digest`.**
  `application/bucket_maintenance/_manifest_digest.py` docstring claims a
  cross-check the importer never performs (digest is used only as AEAD AAD).
  Corroborated by two axes. Note: digest is computed over a payload including
  host-specific timestamps, so a literal recompute can't match without a
  timestamp-independent projection. Fix: implement over a stripped projection or
  correct the docstring.
- **M2 security — file-fallback `master.kdf` accepts unbounded/too-low Argon2
  cost on read.** `master_key/_master_key_records.py` `_KdfParameters` has no
  bounds (the manifest twin `KdfParams` enforces a floor). Fix: apply the same
  validation window on read.
- **M3 enrollment consistency — private route helpers bypass the canonical
  wrapper.** `domain/invoices/_repository.py`, `domain/transactions/_repository.py`,
  `application/user_profile/_repository.py` each define `_secure_objects_for_bucket`
  calling `inspect_bucket_storage_runtime(...).secure_object_repository()` directly
  instead of `secure_object_repository_for_bucket`. No exposure (same substrate);
  route policy duplicated 3×. Fix: consume the top-level wrapper.
- **M4 durability — manifest write omits fsync.** `bucket/_manifest_io.py`
  stages `.tmp` + `os.replace` but never fsyncs the tmp file or parent dir; the
  sibling `_rotation._atomic_write` does. Fix: mirror it (`core.locks.fsync_parent_dir`).
- **M5 concurrency — lockfile stale-reclaim TOCTOU.** `bucket/_lockfile.py`
  `_reclaim_if_stale` unlinks on a previously-read PID with no re-validation; a
  peer's just-acquired live lock can be unlinked. Bounded because the lock does
  not gate row writes. Fix: re-validate PID immediately before the reclaim unlink.
- **M6 audit/privacy — absolute paths in the bucket event log.**
  `application/bucket_maintenance/_service.py` stores `output_path`/`source_path`
  (host-specific absolute) in `BUCKET_EXPORTED`/`BUCKET_IMPORTED` payloads. Fix:
  persist basename only (or omit; the `manifest_digest` is the audit anchor).
- **M7 determinism — `exported_at` in bundle payload.**
  `domain/user_profile/_portable_export.py` `Field(default_factory=utc_now)` makes
  two exports of identical state differ; bundle is not content-addressable. Fix:
  move out of the equality-bearing payload or document as non-payload metadata.
- **M8 performance — N-decrypt namespace scans.** `secure_objects.py`
  `iter_records_with_failures` decrypts every row in Python to recover the natural
  id (object_key is an HMAC digest); `SecureBoundRepository.iter_records`
  materialises+sorts. Fix: add a `HashedLookup` column for attributes that need
  filtering; make `iter_records` streaming.
- **M9 rotation — SQL `secure_objects` possibly outside the rotation plan.**
  `_rotation.py` `default_rotation_plan` enumerates only file-`*.envelope.json`
  consumers. Confirm SQL-store rotation is owned by the bucket-DEK rewrap path and
  document the boundary; if not, add the SQL store to the rotation contract.

## Findings — LOW

- **L1** `core/observability/_store.py` writes `trace.json` plaintext (redacted
  via `diagnostic_rules()`); optional route through the active-bucket wrapper.
- **L2** `adapters/outbound/aeat/sede/_iva_compensation_wallet.py` diagnostic dump
  (default-off, redacted structural metadata only); confirm `_wallet_page_shape_context`
  excludes amounts.
- **L3** `master_key/_master_key.py` standalone `salt` file is write-only (no
  reader) — deletion candidate per `no-legacy-compatibility`.
- **L4** `master_key/_master_key.py` `_write_bytes_secure` is dead code with the
  weaker non-atomic write pattern — remove.
- **L5** `bucket/_manifest.py` `schema_version` has no forward-version ceiling on
  read (partly mitigated by `extra="forbid"`); add a `max_supported_version` check.
- **L6** `sql/engine.py` `_engines` cache keyed by URL survives DB-file
  replacement; dispose on bucket hard-delete.
- **L7** registry `_loader.py` pickle cache lands in world-readable `/tmp`; payload
  is non-sensitive first-party registry schema, keyed by tree fingerprint.

## Remediation sequencing (blast-radius order, per the architecture ADR)

1. Security edges, self-contained: H2, H1, M2, L3, L4.
2. At-rest integrity: H3 (AAD row binding + read-time verification).
3. Concurrency/durability: H5, M4, M5, L6.
4. Correctness/cross-machine: H4, H6, M1, M6, M7, L5.
5. Standardisation/structure/enrollment: H9, H10, H11, M3, M9, plus H8 deletion.
6. Performance: H7, M8.

Each fix lands as one atomic explicit-pathspec commit with a real gate
(`pytest --collect-only -q` clean + the relevant focused suite), authored only
over files with no peer WIP (`git diff -- <file>` before edit). Cross-corroborated
findings (H3, M1) carry the highest confidence.
