# Encrypted SQL repository, revision writes, and workflow storage

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-025` · **Topic:** [Persistence and secure storage](../topics/persistence-and-secure-storage.md)

<!-- preserved:article -->
## Scope

This chunk covers 10 persistence files (3,957 lines; 35,747 measured `o200k_base` proxy tokens): secure-object schema and write operations, SQL engine/session lifecycle, row models and revision hashing, repository read/migration paths, storage path declarations, and workflow persistence. I read all assigned ranges across seven bounded pages. Static inspection only; I did not execute database operations or tests.

## Stored data and user-visible behavior

The main `secure_objects` table holds sensitive payload ciphertext, namespace, HMAC-addressed object key, classification/version, and revision metadata. The payload is encrypted explicitly so AEAD associated data binds it to namespace, object-key digest, and schema version; the natural key does not appear in the table. A separate `transaction_date_index` model is deliberately plaintext and contains only transaction/bucket identifiers and date routing fields. Its comments define it as a rebuildable performance aid: missing or incomplete entries must fall back to a full encrypted scan, and the table must never acquire amounts, counterparties, tax IDs, or descriptions. This chunk contains the schema, while the co-writing and fallback implementation belongs to ledger modules. SQL row models and routing-index contract (`src/cadrumo/adapters/persistence/storage/sql/orm.py`) Encrypted object table (`src/cadrumo/adapters/persistence/storage/sql/orm.py`)

`SecureObjectWriteOperations` is the central write funnel. Direct writes, raw-digest archive restores, and multi-object writes validate UTC timestamps and registered namespace policy, compute the HMAC row identity, encrypt the payload with identity AAD, and derive plaintext/ciphertext hashes. A SQL transaction reads each prior revision, checks any expected revision, derives the successor ID and ancestor list, then performs grouped inserts or updates. Duplicate identities in a batch split the work into ordered chunks so later writes observe the revision written earlier in the same transaction. Updates are guarded by the revision read; if a concurrent writer moved it, the operation detects a row-count mismatch and refuses rather than silently forking lineage. `apply_batch` also combines writes and digest-addressed deletions, and checks read assertions in serializable isolation before mutation. Batch transaction and assertions (`src/cadrumo/adapters/persistence/storage/sql/_secure_object_writes.py`) Identity AAD and pending write (`src/cadrumo/adapters/persistence/storage/sql/_secure_object_writes.py`) Guarded update path (`src/cadrumo/adapters/persistence/storage/sql/_secure_object_writes.py`)

Revision IDs are deterministic SHA-256 digests over namespace, HMAC key, schema version, canonical UTC write time, plaintext/ciphertext hashes, and the direct previous-revision/payload-hash links. Reads recompute this tuple before accepting the decrypted row. That detects edits to those inputs when the revision ID is left alone; it is not keyed authentication against an actor who can rewrite the database and recompute all fields. The guarantee explicitly excludes `revision_ancestor_ids`, `revision_written_at`, `write_provenance`, `source_event_id`, and `conflict_policy`; only the direct parent edge is part of the revision digest, not the ancestry chain behind it. Consumers of these fields should be traced before assigning integrity or audit meaning to them. Revision derivation and covered-field boundary (`src/cadrumo/adapters/persistence/storage/sql/secure_object_crypto.py`) Read-time self-consistency gate (`src/cadrumo/adapters/persistence/storage/sql/secure_object_crypto.py`)

## Read, repair, and schema evolution

Repository reads validate namespace registration, classification, exact version readability, and revision self-consistency before AEAD decryption. Namespace scans offer two contracts: fail-closed listing refuses a corrupt row before yielding any partial readable subset, while failure-aware iterators return one readable/unreadable outcome per row and stream with a configurable batch size. Raw archive scans return encrypted bytes plus metadata for restore or mirroring without decrypting the payload. Migration helpers can load selected current/legacy targets, pass the complete upgraded payload set to a validator, and only then CAS-replace old rows in one batch. A targeted “current version” path checks all selected versions before decrypting/yielding any row, preserving explicit-cutover behavior. Current-only loading and migration (`src/cadrumo/adapters/persistence/storage/sql/secure_objects.py`) Atomic migration flow (`src/cadrumo/adapters/persistence/storage/sql/secure_objects.py`) Fault-isolated scans (`src/cadrumo/adapters/persistence/storage/sql/secure_objects.py`)

The decryptability repair surface probes whether ciphertext opens under current key/AAD and can copy undecryptable rows, with their original ciphertext and metadata, to a quarantine table before deleting them from the active table. It does not auto-delete quarantined material. This is a crypto-layer diagnostic: schema/classification/namespace contracts are separate read gates, so “decryptable” does not mean “valid application record.” Quarantine operation (`src/cadrumo/adapters/persistence/storage/sql/secure_objects.py`) Quarantine table and schema helpers (`src/cadrumo/adapters/persistence/storage/sql/_secure_object_schema.py`)

The workflow adapter stores a singleton workflow-state envelope and per-run result envelopes in the secure-object repository. State writes carry the loaded revision as a CAS expectation; prepared event-catalogue writes likewise preserve revision identity so workflow changes can share a surrounding batch. Reads check inner classification/version and run ID identity. Absent state becomes an empty model with the distinguished absent revision; state saves/deletes invalidate the output-language cache. State read and CAS write preparation (`src/cadrumo/adapters/persistence/workflow.py`) Run envelope identity checks (`src/cadrumo/adapters/persistence/workflow.py`) Run persistence (`src/cadrumo/adapters/persistence/workflow.py`)

## Engine, schema, and operational boundaries

The engine cache keys profile routes by resolved storage root plus bucket ID, with URL-keying reserved for explicit/root-fallback routes. SQLite connections enable foreign keys, a five-second busy timeout, WAL, and `synchronous=NORMAL`; the latter is documented as permitting loss of the last transaction on OS or power failure while preserving database integrity. Bucket engines are disposed by session/bucket lifecycle owners. `get_engine` calls SQLAlchemy `create_all` against current ORM metadata and documents a forward-only schema with no migration history, so this code alone does not supply a tested upgrade path for arbitrary old databases. SQLite configuration and route normalization (`src/cadrumo/adapters/persistence/storage/sql/engine.py`) Engine cache and schema creation (`src/cadrumo/adapters/persistence/storage/sql/engine.py`) Transaction and serializable session behavior (`src/cadrumo/adapters/persistence/storage/sql/session.py`)

The path registry derives fixed layout names from the core storage taxonomy and records grammar, kind, owner, schema version, and path anchor. Some LLM/cache paths are explicitly logical display strings even though they are declared as file-shaped grammar; the code comments state their producers store data in SQL. This inventory documents shape/provenance but should not be read as proof that every grammar is a physical file. Path-definition contract (`src/cadrumo/adapters/persistence/storage/storage_path_definitions.py`) SQL and blob path declarations (`src/cadrumo/adapters/persistence/storage/storage_path_definitions.py`)

## Assessment and follow-up

Strong properties include one write funnel, whole-batch SQL transactions, revision-guarded updates, identity-bound ciphertext, exact namespace/version policies, per-row failure isolation, and explicit quarantine rather than automatic loss. Important limits are that revision metadata is an unkeyed integrity structure with a stated subset of fields covered; raw-key restore cannot check natural-key grammar after that key has been lost; and some listings materialize rows before yielding while the failure-aware path is the bounded streaming alternative. The transaction-date index’s correctness relies on its absent/incomplete fallback and atomic co-write in callers outside this chunk. I did not validate SQLite WAL behavior on all target platforms, concurrent writer outcomes, actual quarantine restoration, or migration compatibility against existing stores.

Synthesis should connect the transaction-date index writer/read fallback, archive restore callers using raw HMAC keys, secure-object namespace registration and migration definitions, and tests that exercise write races and revision-column tampering. It should also establish which consumers rely on ancestry/provenance/event metadata beyond the digest-covered tuple.

## Complete assigned-file coverage

All 10 assigned files were read in full across pages 1–7.

- sql/_secure_object_schema.py (110 lines) (`src/cadrumo/adapters/persistence/storage/sql/_secure_object_schema.py`)
- sql/_secure_object_writes.py (835 lines) (`src/cadrumo/adapters/persistence/storage/sql/_secure_object_writes.py`)
- sql/engine.py (339 lines) (`src/cadrumo/adapters/persistence/storage/sql/engine.py`)
- sql/orm.py (193 lines) (`src/cadrumo/adapters/persistence/storage/sql/orm.py`)
- sql/secure_object_crypto.py (134 lines) (`src/cadrumo/adapters/persistence/storage/sql/secure_object_crypto.py`)
- sql/secure_object_records.py (149 lines) (`src/cadrumo/adapters/persistence/storage/sql/secure_object_records.py`)
- sql/secure_objects.py (1,293 lines) (`src/cadrumo/adapters/persistence/storage/sql/secure_objects.py`)
- sql/session.py (74 lines) (`src/cadrumo/adapters/persistence/storage/sql/session.py`)
- storage_path_definitions.py (526 lines) (`src/cadrumo/adapters/persistence/storage/storage_path_definitions.py`)
- workflow.py (304 lines) (`src/cadrumo/adapters/persistence/workflow.py`)
<!-- /preserved:article -->
