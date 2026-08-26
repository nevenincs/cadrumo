---
generated: true
tags:
  - '#index'
  - '#storage-backend-security-review'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:54f10889c014800b38ab75ec750e13c80e0d5cb1f9f97ecc6d81162014c8f59e'
related:
  - '[[2026-06-14-storage-backend-security-review-adr]]'
  - '[[2026-06-14-storage-backend-security-review-plan]]'
  - '[[2026-06-14-storage-backend-security-review-research]]'
  - '[[2026-06-15-storage-backend-security-review-audit]]'
---

# `storage-backend-security-review` feature index

Auto-generated index of all documents tagged with `#storage-backend-security-review`.

## Documents

### adr

- `2026-06-14-storage-backend-security-review-adr` - `storage-backend-security-review` adr: `close the residual secure-storage security, enrollment, and standardisation gap` | (**status:** `accepted`)

### audit

- `2026-06-15-storage-backend-security-review-audit` - `storage-backend-security-review` audit: `campaign close honesty review`

### exec

- `2026-06-14-storage-backend-security-review-W01-P01-S01` - Replace export-archive HKDF sealing-key derivation with Argon2id and persist the kdf params in the recovery-wrap member
- `2026-06-14-storage-backend-security-review-W01-P01-S02` - Add a strict export then import roundtrip test over the Argon2id-sealed archive with a non-default passphrase
- `2026-06-14-storage-backend-security-review-W01-P02-S03` - Accept an in-memory binary stream in the bbox declaration parse path so no decrypted bytes touch disk
- `2026-06-14-storage-backend-security-review-W01-P02-S04` - Delete the temporary sensitive PDF helper and fold the bbox branch into the in-memory bytes path
- `2026-06-14-storage-backend-security-review-W01-P03-S05` - Apply the manifest KDF validation window to the file-fallback parameters on read and reject below-floor Argon2 cost
- `2026-06-14-storage-backend-security-review-W01-P03-S06` - Delete the dead non-atomic _write_bytes_secure method and its sensitive-persistence-policy allowlist entries
- `2026-06-14-storage-backend-security-review-W02-P04-S07` - Bind namespace and object-key digest and schema version into the secure-object payload AEAD associated data
- `2026-06-14-storage-backend-security-review-W02-P04-S09` - Add a row-substitution and corrupted-hash anti-tautology test proving read-time refusal
- `2026-06-14-storage-backend-security-review-W03-P05-S10` - Set SQLite busy_timeout in the bucket engine connect listener so a concurrent invocation waits rather than failing immediately with database-locked
- `2026-06-14-storage-backend-security-review-W03-P05-S11` - Add a concurrent-writer regression proving two sessions on one bucket do not raise an immediate database-locked error
- `2026-06-14-storage-backend-security-review-W03-P06-S12` - fsync the staged tmp file and the parent directory before and after os.replace on the manifest write
- `2026-06-14-storage-backend-security-review-W03-P06-S13` - Re-read and re-validate the holder PID immediately before the stale-lock reclaim unlink
- `2026-06-14-storage-backend-security-review-W03-P06-S14` - Dispose the cached engine when a bucket DB is hard-deleted so a recreated file does not reuse stale connections
- `2026-06-14-storage-backend-security-review-W04-P07-S15` - Replace the resolved absolute source_path provenance with a relative filename or sha-only reference in the raw transaction model
- `2026-06-14-storage-backend-security-review-W04-P07-S16` - Add a cross-OS transaction provenance roundtrip test proving rehydration does not mutate the persisted shape
- `2026-06-14-storage-backend-security-review-W04-P08-S17` - Move exported_at out of the equality-bearing portable bundle payload
- `2026-06-14-storage-backend-security-review-W04-P08-S18` - Persist basename-only paths in the bucket exported and imported event payloads
- `2026-06-14-storage-backend-security-review-W04-P09-S19` - Compare the manifest label against the record display_name in verify_profile_integrity and raise on divergence
- `2026-06-14-storage-backend-security-review-W04-P09-S20` - Implement the manifest-digest cross-check over a timestamp-independent projection or correct the contract docstring
- `2026-06-14-storage-backend-security-review-W05-P10-S21` - Route every domain and outbound secure-object namespace literal through its STORAGE_NAMESPACE_REGISTRY definition constant
- `2026-06-14-storage-backend-security-review-W05-P10-S22` - Extend the namespace adoption gate to scan domain and adapters outbound in addition to application
- `2026-06-14-storage-backend-security-review-W05-P11-S23` - Resolve the fincas domain hexagonal inversion by relocating the ORM-coupled repository or exposing a typed boundary facade and fix the stale docstring path
- `2026-06-14-storage-backend-security-review-W05-P11-S24` - Rebind the private bucket-submodule imports in profile health and overview to the bucket package surface
- `2026-06-14-storage-backend-security-review-W05-P12-S26` - Replace the three private secure-objects-for-bucket route helpers with the canonical secure_object_repository_for_bucket wrapper
- `2026-06-14-storage-backend-security-review-W05-P12-S27` - Delete the v1 portable-bundle compat branch and drop version 1 from the supported set per no-legacy-compatibility
- `2026-06-14-storage-backend-security-review-W05-P12-S28` - Confirm the SQL secure_objects store is covered by the bucket-DEK rewrap rotation path and document or extend the rotation contract
- `2026-06-14-storage-backend-security-review-W06-P13-S29` - Remove the attach_evidence double full-catalogue decrypt by threading one decrypted catalogue through the command
- `2026-06-14-storage-backend-security-review-W01-P03-S32` - OWNER-GATED DEFERRED: remove the write-only standalone salt artefact and shrink the torn-install detection tuple after owner review per the no-legacy-compatibility key-management caution
- `2026-06-14-storage-backend-security-review-W02-P04-S08` - Verify the stored payload hash and recomputed revision id on every secure-object read and fail closed on mismatch
- `2026-06-14-storage-backend-security-review-W03-P05-S33` - LARGER FOLLOW-UP: enable journal_mode=WAL and synchronous=NORMAL after migrating the ~21 at-rest raw-db test readers to a shared WAL-aware helper that also scans the -wal sidecar
- `2026-06-14-storage-backend-security-review-W05-P11-S25` - Promote the sealed-archive read and write helpers to the bucket package all and rebind the maintenance service call sites
- `2026-06-14-storage-backend-security-review-W06-P14-S30` - Make secure-object namespace enumeration stream decrypted rows instead of materialising and sorting the full set
- `2026-06-14-storage-backend-security-review-W06-P14-S31` - Move the transaction catalogue to one secure-object row per transaction keyed by transaction id so single-row mutations stop rewriting the whole catalogue

### plan

- `2026-06-14-storage-backend-security-review-plan` - `storage-backend-security-review` plan

### research

- `2026-06-14-storage-backend-security-review-research` - `storage-backend-security-review` research: `secure storage backend adversarial and structural audit`
