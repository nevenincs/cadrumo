# Encrypted blobs, bucket archives, and custody filesystem

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-020` · **Topic:** [Persistence and secure storage](../topics/persistence-and-secure-storage.md)

<!-- preserved:article -->
## Scope

This chunk contains 24 storage adapters and filesystem primitives for attachment blobs, bucket export archives, cryptographic records, and profile-custody capsules. I read every assigned line across nine bounded pages: 5,121 lines and 47,496 measured `o200k_base` proxy tokens. Static source review only; I did not run the application or tests.

## Attachments and encrypted blob storage

`AttachmentStore` keeps document bytes in the encrypted secure-object substrate as FINANCIAL content-addressed blobs. It frames raw bytes before persistence so the secure-object payload hash does not directly reveal a document’s SHA-256, while the natural key is HMAC-digested. Manifests are encrypted envelopes. Reads validate digest syntax, manifest-to-row identity, profile bucket ownership, byte count, and blob digest; listing also checks the manifest’s claimed digest against its hashed row key and verifies that referenced bytes exist. Duplicate ingestions of identical bytes merge transaction and invoice links, keep the earliest capture time, and preserve the first source metadata. Blob framing and content-addressed writes (`src/cadrumo/adapters/persistence/storage/attachment.py`) Manifest merge behavior (`src/cadrumo/adapters/persistence/storage/attachment.py`) Manifest write and validation paths (`src/cadrumo/adapters/persistence/storage/attachment.py`)

The merge is a read/merge/write sequence: `_merge_with_stored_manifest` runs before `_write` invokes the optional mutation writer around the final save. Concurrent ingestions could therefore both merge against the same old manifest and lose one set of newly accumulated links unless a caller-level lock covers the whole `write_manifest` operation. The adapter itself does not pass a revision witness to `save`; review the actual call boundary for that serialization invariant. This is a scoped concurrency concern, not evidence that production commands can race. Read/merge precedes the gated save (`src/cadrumo/adapters/persistence/storage/attachment.py`) Mutation-writer scope (`src/cadrumo/adapters/persistence/storage/attachment.py`)

The separate filesystem blob store writes CORPUS-class bytes in plaintext only when the classification policy permits it; every other class gets a fresh DEK, AES-256-GCM ciphertext, and a DEK wrapped by the active bucket key. It verifies both ciphertext and plaintext digests, declared plaintext length, envelope/payload classification agreement, and manifest identity against its filename. Per-file writes use atomic replacement, and a caught manifest-write failure removes an untracked new blob or restores the displaced payload bytes. However, payload and manifest are separate files: an abrupt process termination after replacing a blob but before publishing its new manifest can leave a mismatched pair that reads fail closed. Recovery/re-put behavior for that crash window is a useful follow-up. Classification-driven write path (`src/cadrumo/adapters/persistence/storage/blob_store/blob_store.py`) Manifest coherence and path binding (`src/cadrumo/adapters/persistence/storage/blob_store/blob_store.py`) Ciphertext digest and decryption checks (`src/cadrumo/adapters/persistence/storage/blob_store/blob_store.py`)

The shared AEAD layer uses AES-256-GCM with random 12-byte nonces and HKDF-SHA256 for purpose-specific derivation. Secure-object ciphertext binds namespace, hashed object key, and schema version as associated data; deterministic HMAC lookup is documented as unsuitable for low-entropy values because equality/frequency remains visible. Typed AEAD and HKDF operations (`src/cadrumo/adapters/persistence/storage/crypto/aead.py`) Row-bound secure-object AAD (`src/cadrumo/adapters/persistence/storage/crypto/encrypted_columns.py`) Hashed-lookup disclosure limits (`src/cadrumo/adapters/persistence/storage/crypto/encrypted_columns.py`)

## Bucket layout, archives, and locking

Bucket path helpers reject empty, dotted, separator-bearing, and drive-qualified path components before joining them. Keystore paths are required to remain outside the bucket tree and database, and sidecar filenames are validated at the join point. Path-component validation (`src/cadrumo/adapters/persistence/storage/bucket/directory_layout.py`) Keystore separation and sidecar join (`src/cadrumo/adapters/persistence/storage/bucket/keystore_paths.py`)

The lockfile uses exclusive creation, local thread ownership and re-entry tracking, stale-PID reclaim with a second PID read before unlink, and bounded polling. Release removes only a lock naming the current process; on Windows, a blocked unlink is retried so a live PID does not leave a permanently wedged bucket. Atomic claim and stale reclaim (`src/cadrumo/adapters/persistence/storage/bucket/lockfile.py`) Acquire/release lifecycle (`src/cadrumo/adapters/persistence/storage/bucket/lockfile.py`)

Bucket archives have a strict versioned header and exactly two ordered members. The writer stages beside the destination, normalizes tar metadata, refuses overwrite/empty payloads, atomically publishes, and fsyncs the parent directory. The reader rejects wrong suffixes, malformed headers, non-regular or extra members, empty members, and member decompression beyond 512 MiB; it returns encrypted payload bytes without interpreting them, leaving manifest-digest verification to the importer. One resource-bound review point remains: after reading the header it calls `getmembers()` and materializes the archive’s entire member list before rejecting a noncanonical layout. The per-member byte ceiling does not bound the number of tiny tar entries or total decompressed metadata, so consider a bounded member-count/streaming check for operator-supplied archives. Strict archive read and layout check (`src/cadrumo/adapters/persistence/storage/bucket/sealed_archive_reader.py`) Whole-layout validation (`src/cadrumo/adapters/persistence/storage/bucket/sealed_archive_reader.py`) Staged durable archive write (`src/cadrumo/adapters/persistence/storage/bucket/sealed_archive_writer.py`)

## Profile-custody filesystem

Capsule data paths are validated under both POSIX and Windows interpretations, entry count and file size are capped, and writes create files exclusively without following links. In-place capsule-file replacement compares the authenticated old-byte digest, writes a same-directory staged file, renames it, and fsyncs the directory. Filesystem record CAS routines have platform-specific anchored implementations and fail closed where the required atomic primitive is unavailable. Portable path and bounded data inventory (`src/cadrumo/adapters/persistence/storage/custody/_capsule_data.py`) Authenticated-byte compare-and-swap (`src/cadrumo/adapters/persistence/storage/custody/_capsule_data.py`) Cross-platform local-record CAS (`src/cadrumo/adapters/persistence/storage/custody/_filesystem_records.py`)

The capsule inventory walks without following links/reparse points and bounds entry count, individual files, and total size. It hashes ordinary custody records by path and bytes, but deliberately excludes SQLite WAL/SHM and the holder lockfile, and covers the database only by path. The source documents why: closing a connection checkpoints WAL contents and makes raw database bytes vary without logical writes. The explicit remaining limitation is that database rows written between deletion preflight and execution do not change the inventory digest; nothing in this adapter catches that change. This scope boundary should be considered wherever the digest is used as a destructive-operation precondition. Inventory coverage contract (`src/cadrumo/adapters/persistence/storage/custody/_inventory.py`) Digest projection (`src/cadrumo/adapters/persistence/storage/custody/_inventory.py`)

## Assessment and limits

The strongest design properties are content-address and row-identity binding, classification-driven encryption, path containment, bounded no-follow capsule operations, explicit archive framing, and platform-specific CAS rather than unguarded overwrites. Review follow-ups are the attachment read/merge/write caller invariant, blob/manifest crash recovery, archive member-count bounds, and the documented custody-inventory gap for concurrent database changes. I did not validate filesystem behavior on POSIX or Windows, crash behavior, importer-side archive digest enforcement, key protection outside these adapters, or the runtime reachability of the attachment concurrency case.

## Complete source coverage

All 24 assigned files were read in full across pages 1–9.

- attachment.py (539 lines) (`src/cadrumo/adapters/persistence/storage/attachment.py`)
- blob_store/__init__.py (18 lines) (`src/cadrumo/adapters/persistence/storage/blob_store/__init__.py`)
- blob_store.py (717 lines) (`src/cadrumo/adapters/persistence/storage/blob_store/blob_store.py`)
- materialisation.py (102 lines) (`src/cadrumo/adapters/persistence/storage/blob_store/materialisation.py`)
- bucket/__init__.py (44 lines) (`src/cadrumo/adapters/persistence/storage/bucket/__init__.py`)
- _sealed_archive_errors.py (60 lines) (`src/cadrumo/adapters/persistence/storage/bucket/_sealed_archive_errors.py`)
- directory_layout.py (139 lines) (`src/cadrumo/adapters/persistence/storage/bucket/directory_layout.py`)
- errors.py (116 lines) (`src/cadrumo/adapters/persistence/storage/bucket/errors.py`)
- export_archive_header.py (84 lines) (`src/cadrumo/adapters/persistence/storage/bucket/export_archive_header.py`)
- keystore_paths.py (153 lines) (`src/cadrumo/adapters/persistence/storage/bucket/keystore_paths.py`)
- lockfile.py (568 lines) (`src/cadrumo/adapters/persistence/storage/bucket/lockfile.py`)
- output_language_hint.py (85 lines) (`src/cadrumo/adapters/persistence/storage/bucket/output_language_hint.py`)
- sealed_archive_reader.py (259 lines) (`src/cadrumo/adapters/persistence/storage/bucket/sealed_archive_reader.py`)
- sealed_archive_writer.py (189 lines) (`src/cadrumo/adapters/persistence/storage/bucket/sealed_archive_writer.py`)
- certificate_secret_backend.py (126 lines) (`src/cadrumo/adapters/persistence/storage/certificate_secret_backend.py`)
- crypto/__init__.py (6 lines) (`src/cadrumo/adapters/persistence/storage/crypto/__init__.py`)
- aead.py (195 lines) (`src/cadrumo/adapters/persistence/storage/crypto/aead.py`)
- aes_gcm.py (71 lines) (`src/cadrumo/adapters/persistence/storage/crypto/aes_gcm.py`)
- encrypted_columns.py (192 lines) (`src/cadrumo/adapters/persistence/storage/crypto/encrypted_columns.py`)
- custody/__init__.py (6 lines) (`src/cadrumo/adapters/persistence/storage/custody/__init__.py`)
- _capsule_data.py (235 lines) (`src/cadrumo/adapters/persistence/storage/custody/_capsule_data.py`)
- _capsule_filesystem.py (319 lines) (`src/cadrumo/adapters/persistence/storage/custody/_capsule_filesystem.py`)
- _filesystem_records.py (498 lines) (`src/cadrumo/adapters/persistence/storage/custody/_filesystem_records.py`)
- _inventory.py (400 lines) (`src/cadrumo/adapters/persistence/storage/custody/_inventory.py`)
<!-- /preserved:article -->
