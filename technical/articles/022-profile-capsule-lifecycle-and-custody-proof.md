# Profile capsule lifecycle and custody proof

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-022` · **Topic:** [Persistence and secure storage](../topics/persistence-and-secure-storage.md)

<!-- preserved:article -->
## Scope

This chunk covers 12 custody modules for capsule publication and discovery, local record operations, GNOME collection checks, password KDF calibration, and label-head records. I read all assigned code across nine bounded pages: 5,182 lines and 46,045 measured `o200k_base` proxy tokens. Static source review only; I did not run OS-specific filesystem, keyring, or KDF paths.

## Capsule publication, discovery, and mutation

Capsule creation builds a complete sibling staging directory containing the password envelope, DEK sentinel, selected data files, and a small canonical commit marker. On Linux it writes through pinned directory descriptors and publishes with no-replace `renameat2`; on Windows it anchors the stage/root handles and uses a no-replace handle rename plus the platform’s durability fence. The commit is written last, after files and child directories are flushed, and the capsule only becomes discoverable at publication. Transaction-owned staged publication permits a journal to inventory/verify the exact stage before its sole rename. Capsule stage and publish path (`src/cadrumo/adapters/persistence/storage/custody/capsule.py`) POSIX descriptor-relative publication (`src/cadrumo/adapters/persistence/storage/custody/capsule.py`) Verified staged publication (`src/cadrumo/adapters/persistence/storage/custody/capsule.py`)

Discovery accepts only canonical UUID-named directories with a bounded, current commit marker whose embedded profile ID matches the directory. Scans avoid following links and retain the anchored marker observation when also reading the optional summary label. A separate exact-path detector refuses stores with retired plaintext bucket manifests or retired `bucket.dek.json` key material; it only checks existence, does not parse or disclose retired contents, and reports the roots/patterns needed for destructive reset guidance. Current capsule recognition (`src/cadrumo/adapters/persistence/storage/custody/capsule.py`) Anchored current-marker discovery (`src/cadrumo/adapters/persistence/storage/custody/capsule_discovery.py`) Retired-layout refusal (`src/cadrumo/adapters/persistence/storage/custody/capsule_discovery.py`)

Password rotation is constrained to the same DEK epoch, the committed envelope’s direct self-digest predecessor, and exactly the next password generation. Recovery enrollment is exclusive and must bind the active epoch; revocation compares the caller’s observed digest before removal. Normal password reads bring back commit, envelope, and sentinel through anchored no-follow reads, then check profile and epoch alignment. These contracts protect the DEK/recovery relationship while keeping normal password reads independent of the recovery path. Rotation lineage and epoch fence (`src/cadrumo/adapters/persistence/storage/custody/capsule.py`) Recovery install and remove (`src/cadrumo/adapters/persistence/storage/custody/capsule.py`) Normal password material read (`src/cadrumo/adapters/persistence/storage/custody/capsule.py`)

Local deletion writes an exclusive transaction marker bound to profile, transaction ID, and a capsule inventory digest; the capsule is renamed to a unique tombstone and checked before safe removal. Inventory coverage is deliberately asymmetric: ordinary custody members are content-bound, while the SQLite database is present-by-path only and WAL/SHM and holder lock are excluded. That database-content gap is documented in the inventory implementation and remains a boundary on what the deletion precondition proves. Deletion marker and tombstone verification (`src/cadrumo/adapters/persistence/storage/custody/capsule.py`) Rename and safe tombstone removal (`src/cadrumo/adapters/persistence/storage/custody/capsule.py`) Inventory coverage limitation (`src/cadrumo/adapters/persistence/storage/custody/_inventory.py`)

## Canonical records, locking, and label provenance

Commit and deletion records enforce strict schemas, small byte ceilings, duplicate-key/non-finite JSON refusal, canonical byte spelling, and self-digest consistency. Label records carry a revision chain plus a content digest and a wider self digest that includes the content digest. These unkeyed hashes detect inconsistent or accidental changes but are not a MAC or signature against an actor who can rewrite the file and recompute the hashes. Labels are a locked-profile-readable projection; they do not themselves establish password authority. Commit and label record construction (`src/cadrumo/adapters/persistence/storage/custody/capsule_records.py`) Canonical commit parsing (`src/cadrumo/adapters/persistence/storage/custody/capsule_records.py`) Shared self-digest contract (`src/cadrumo/adapters/persistence/storage/custody/digest_model.py`)

The label-head model supplies a separate trusted revision witness, requiring the next label to extend both the revision and prior content digest. A pending-advance record binds expected/replacement labels and the replacement head so a higher-level store can recover a write interrupted between the label and head. The model defines this witness, while its persistence/recovery caller is outside this chunk. Label-head chain checks (`src/cadrumo/adapters/persistence/storage/custody/label_head_models.py`) Pending label advance witness (`src/cadrumo/adapters/persistence/storage/custody/label_head_models.py`)

Filesystem helpers use anchored parent directories, no-follow regular-file reads, bounded payloads, kernel-owned local locks, exact-byte compare-and-swap, and platform-specific rename/exchange operations. The root lock is re-entrant only for the same process/thread/root; leaf locks use `flock` on POSIX and non-shared handles on Windows. Unsupported atomic operations refuse instead of degrading to a path-based check-then-write. Root lifecycle lock (`src/cadrumo/adapters/persistence/storage/custody/filesystem.py`) Anchored local-record CAS (`src/cadrumo/adapters/persistence/storage/custody/filesystem.py`) Directory identity primitives (`src/cadrumo/adapters/persistence/storage/custody/filesystem_primitives.py`)

## GNOME protection and password KDF calibration

The GNOME check is a read-only suitability probe for one selected Secret Service collection. It validates canonical collection-path encoding; checks the selected D-Bus owner, process, and protected control directory; authenticates the local PKCS#11 metadata socket peer; and reads only collection attributes to establish persistent, trusted, unlocked status. It does not request the master secret, prompt, mutate, or prove password strength. The module explicitly notes that separate metadata and Secret Service calls cannot atomically exclude a concurrent password change. GNOME collection admission probe (`src/cadrumo/adapters/persistence/storage/custody/gnome_collection_protection.py`)

KDF enrollment searches a finite Argon2id grid and chooses the strongest eligible point whose confirmed median lies within the target band. A near-over-limit sample is repeated, an in-band point receives five confirmation samples, and timeout/resource failure falls back to a fixed 64 MiB / 3 iteration point that is also the minimum strength floor. Calibration has an overall deadline and serializes KDF work with thread and OS-level leases. Password and recovery unwraps use the supervised worker and verify the DEK sentinel in the parent before returning a key. Finite-grid ordering (`src/cadrumo/adapters/persistence/storage/custody/kdf_calibration_search.py`) Calibration and fallback policy (`src/cadrumo/adapters/persistence/storage/custody/kdf_supervision.py`) Sentinel-checked password unwrap (`src/cadrumo/adapters/persistence/storage/custody/kdf_supervision.py`) KDF lease (`src/cadrumo/adapters/persistence/storage/custody/kdf_supervision.py`)

## Assessment and limits

The strongest patterns are one-rename publication, anchored/no-follow filesystem access, explicit old-format refusal, direct-successor password rotation, sentinel-proven DEKs, and independent label revision witnesses. Important boundaries are that record self-digests are unkeyed, the database portion of deletion inventory does not bind content, and lifecycle locks for some capsule mutation APIs are a caller contract. I did not verify the higher-level label-head recovery state machine, database concurrency during deletion, cross-platform atomic-rename availability beyond the code paths, GNOME protocol compatibility, or measured KDF performance.

## Complete source coverage

All 12 assigned files were read in full across pages 1–9.

- capsule.py (1,243 lines) (`src/cadrumo/adapters/persistence/storage/custody/capsule.py`)
- capsule_discovery.py (574 lines) (`src/cadrumo/adapters/persistence/storage/custody/capsule_discovery.py`)
- capsule_records.py (442 lines) (`src/cadrumo/adapters/persistence/storage/custody/capsule_records.py`)
- digest_model.py (118 lines) (`src/cadrumo/adapters/persistence/storage/custody/digest_model.py`)
- envelope.py (49 lines) (`src/cadrumo/adapters/persistence/storage/custody/envelope.py`)
- errors.py (112 lines) (`src/cadrumo/adapters/persistence/storage/custody/errors.py`)
- filesystem.py (772 lines) (`src/cadrumo/adapters/persistence/storage/custody/filesystem.py`)
- filesystem_primitives.py (449 lines) (`src/cadrumo/adapters/persistence/storage/custody/filesystem_primitives.py`)
- gnome_collection_protection.py (423 lines) (`src/cadrumo/adapters/persistence/storage/custody/gnome_collection_protection.py`)
- kdf_calibration_search.py (145 lines) (`src/cadrumo/adapters/persistence/storage/custody/kdf_calibration_search.py`)
- kdf_supervision.py (654 lines) (`src/cadrumo/adapters/persistence/storage/custody/kdf_supervision.py`)
- label_head_models.py (201 lines) (`src/cadrumo/adapters/persistence/storage/custody/label_head_models.py`)
<!-- /preserved:article -->
