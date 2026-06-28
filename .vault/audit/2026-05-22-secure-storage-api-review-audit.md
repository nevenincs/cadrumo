---
tags:
  - '#audit'
  - '#secure-storage-api'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-04-27-secure-persistence-foundation-adr]]'
  - '[[2026-05-06-secure-persistence-enforcement-adr]]'
  - '[[2026-05-14-secure-backend-passkey-custody-adr]]'
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
---



# `secure-storage-api` Code Review



SECURE-STORAGE-001 | CRITICAL | Silent master-key minting still bypasses explicit enrollment
The accepted custody design requires explicit operator enrollment before protected storage is minted. The implementation still has generic master-key resolution paths that fetch or mint a master key on demand in `src/aeat/adapters/persistence/storage/master_key/_master_key.py` at `KeyringMasterKeyProvider.get_master_key`, `FileFallbackMasterKeyProvider.get_master_key`, and `_mint_new`. Profile creation and wizard creation reach those paths from `src/aeat/entrypoints/cli/_config/__init__.py` and `src/aeat/application/wizard/_commands.py`. This preserves the previous silent-enrollment failure mode: the operator can create encrypted state before passphrase confirmation, recovery-code verification, and data-loss acknowledgement have happened. Remediation should make unprovisioned custody fail closed everywhere except the explicit enrollment command, and should move key minting behind the accepted `aeat config init` flow.

SECURE-STORAGE-002 | CRITICAL | Recovery and lock custody primitives are implemented but not exposed through the accepted API
Recovery primitives exist under `src/aeat/adapters/persistence/storage/master_key/_recovery.py` and `src/aeat/adapters/persistence/storage/master_key/_recovery_facade.py`, but the `aeat config` CLI surface in `src/aeat/entrypoints/cli/_config/__init__.py` exposes profile, repair, auth, and bucket verbs without the accepted `unlock`, `lock`, `rekey`, `recover`, `show-recovery`, or `verify-recovery` verbs. Error text in `src/aeat/adapters/persistence/storage/master_key/_master_key.py` and `src/aeat/adapters/persistence/storage/errors.py` still directs operators to nonexistent `aeat security recover` and `aeat security provision` commands. This makes passphrase loss, torn key files, and recovery verification operationally dead-ended. Remediation should wire the accepted `aeat config` verbs and replace every dead `aeat security` suggestion with a command that exists.

SECURE-STORAGE-003 | CRITICAL | Per-bucket custody is not enforced by the encryption key schedule
The storage model has per-bucket manifests and per-bucket database directories, but the active encryption path still activates a provider-level key as both KEK and DEK in `src/aeat/adapters/persistence/storage/master_key/_master_key.py`. The keyring identity is global rather than bucket-scoped, and `_provider_enter` opens `BucketSession` with the same `key_bytes` for both `kek` and `dek`. Profile creation writes per-bucket KDF parameters and recovery flags in `src/aeat/application/user_profile/_profile_repository.py`, but those manifest parameters are not used to unwrap a distinct per-bucket data-encryption key for row encryption. A compromise or accidental rotation of the provider key therefore crosses bucket boundaries. Remediation should introduce a distinct per-bucket DEK, wrap it with a passphrase-derived or keyring-cached KEK scoped by bucket UUID, and make `BucketSession` carry only the unwrapped bucket DEK for row encryption.

SECURE-STORAGE-004 | HIGH | Session freshness and idle-lock enforcement are inconsistent
`SecureObjectRepository` calls `_check_session_freshness` on `load`, `save`, `save_many`, and `delete`, but decryption-capable listing APIs skip that gate: `list_records`, `iter_records_with_failures`, `probe_namespace_integrity`, and metadata / raw iteration paths in `src/aeat/adapters/persistence/storage/sql/secure_objects.py` can inspect or decrypt after the active session should have expired. `save_with_raw_key` also bypasses the freshness gate. Separately, provider activation hard-codes a 60-minute idle window while configuration declares a 15-minute default. Remediation should centralize expiry enforcement in `get_active_master_key` or at every repository entrypoint, and source the idle window from the bucket manifest or settings.

SECURE-STORAGE-005 | HIGH | Unsecured backend canary is not enforced at the persistence boundary
`UnsecuredMasterKeyProvider` exposes a published deterministic key and can be selected through `aeat_secret_store_backend=unsecured` when `AEAT_ALLOW_UNENCRYPTED=1`. The intended `refuse_unsecured_with_real_nif` guard exists in `src/aeat/adapters/persistence/storage/master_key/_master_key.py`, but the audit found no general production caller on `SecureObjectRepository`, master-key activation, or profile load/save paths. That leaves real operator identity and financial records at risk of being sealed with a public key when the unsafe backend is accidentally enabled. Remediation should remove unsecured mode from production resolution or enforce the real-identity canary at activation and secure-object read/write boundaries.

SECURE-STORAGE-006 | HIGH | Sensitive bucket-local JSON stores are allowlisted outside the secure-object backend
The secure-persistence enforcement ADR makes encrypted SQL secure objects the mandatory boundary for governed sensitive records, but the policy allowlist currently accepts direct bucket-local JSON / JSONL writers in `src/aeat/application/evidence/_service.py`, `src/aeat/application/ledger/_evidence.py`, `src/aeat/application/ledger/_business_operation_invoice.py`, `src/aeat/application/inventory/_service.py`, `src/aeat/application/live/_verify.py`, and `src/aeat/application/live/_snapshot_base.py`. These surfaces can carry invoices, evidence bundles, inventory records, and live AEAT observations. Even if the bucket directory is operator-local, the current shape creates a parallel plaintext persistence class with weaker schema, retention, crypto, and repair semantics than `SecureObjectRepository`. Remediation should either migrate these stores to secure objects or record a new accepted exception with explicit data classification, threat model, retention, and export intent.

SECURE-STORAGE-007 | HIGH | Explicit database URLs bypass active-bucket route protections
`Settings` can classify an explicitly supplied `aeat_database_url` as `EXPLICIT_DATABASE_URL` before bucket-root inference in `src/aeat/core/config.py`. The CLI root-fallback guard in `src/aeat/entrypoints/cli/__init__.py` blocks only `ROOT_FALLBACK_DATABASE`, not arbitrary explicit SQLite URLs. This is useful for tests, but as a production path it can route secure-object writes away from the active profile bucket and defeat per-bucket isolation. Remediation should reject explicit database URLs for normal CLI write surfaces unless a test or maintenance mode is explicitly active and audited.

SECURE-STORAGE-008 | MEDIUM | `list_records` fails open on unreadable rows
`SecureObjectRepository.list_records` deliberately suppresses unreadable rows and logs a warning while yielding the readable subset. For catalogue-like stores this can produce partial state, causing downstream services to make decisions from incomplete financial, identity, or workflow data. The typed `iter_records_with_failures` API is safer, but most consumers use `list_records` because it has the simpler contract. Remediation should make default listing fail closed for sensitive classes, or require callers to opt into partial results and handle the unreadable count explicitly.

SECURE-STORAGE-009 | MEDIUM | Secure-object records have schema versions but no object revision lineage
The SQL shape in `src/aeat/adapters/persistence/storage/sql/_orm.py` stores `namespace`, hashed `object_key`, `classification`, `schema_version`, `written_at`, and encrypted `payload`. This validates payload schema compatibility but does not model object revision ids, previous revision hashes, compare-and-swap tokens, or source attribution. Upserts can silently overwrite prior object bodies, and remote sync / repair cannot distinguish expected supersession from conflicting concurrent mutation using storage metadata alone. Remediation should add a storage-level revision or integrity lineage model, especially for profile state, model filing catalogues, AEAT pull snapshots, and remote sync.

SECURE-STORAGE-010 | MEDIUM | Namespace definitions are distributed constants without a registry
Consumers define namespace strings locally across domain, application, adapter, and outbound modules. The audit found generally consistent naming and broad enrollment, but repair attribution in `src/aeat/application/repair_integrity.py` still relies on marker heuristics and `unknown` fallbacks, while the secure-object integrity plan tracks remaining namespace-classification gaps. This means namespace hierarchy, ownership, expected sensitivity class, schema version, retention, and object-key grammar are not centrally auditable. Remediation should introduce a typed secure-object namespace registry and make repositories derive constants from that registry instead of independent string literals.

SECURE-STORAGE-011 | MEDIUM | `iter_records_with_failures` eagerly materializes whole namespaces
`SecureObjectRepository.iter_records_with_failures` executes the namespace query with `.all()` before per-row classification and decryptability handling. Large attachment, ledger, snapshot, or sync namespaces can spike memory and delay failure reporting. Remediation should stream rows with bounded batches, preserving the typed per-row success/failure contract.

SECURE-STORAGE-012 | MEDIUM | Passphrase handling and redaction remain weaker than the custody model expects
`src/aeat/adapters/persistence/storage/master_key/_master_key.py` intentionally reads `AEAT_SECRET_PASSPHRASE` without removing it from process environment, so child processes inherit it. The logging redactor in `src/aeat/core/logging.py` also redacts assignment-shaped secrets only through a whitespace-limited pattern, while passphrases may contain interior whitespace. Remediation should treat environment passphrases as one-shot bootstrap material where feasible, add safer noninteractive secret input, and strengthen redaction to cover quoted and multi-word secret assignments.
