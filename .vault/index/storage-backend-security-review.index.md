---
generated: true
tags:
  - '#index'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
related:
  - '[[2026-06-14-storage-backend-security-review-W01-P02-S03]]'
  - '[[2026-06-14-storage-backend-security-review-W01-P02-S04]]'
  - '[[2026-06-14-storage-backend-security-review-W01-P03-S05]]'
  - '[[2026-06-14-storage-backend-security-review-W01-P03-S06]]'
  - '[[2026-06-14-storage-backend-security-review-W03-P05-S10]]'
  - '[[2026-06-14-storage-backend-security-review-W03-P05-S11]]'
  - '[[2026-06-14-storage-backend-security-review-W03-P06-S12]]'
  - '[[2026-06-14-storage-backend-security-review-W03-P06-S13]]'
  - '[[2026-06-14-storage-backend-security-review-W04-P07-S15]]'
  - '[[2026-06-14-storage-backend-security-review-W04-P07-S16]]'
  - '[[2026-06-14-storage-backend-security-review-W04-P09-S19]]'
  - '[[2026-06-14-storage-backend-security-review-W05-P11-S24]]'
  - '[[2026-06-14-storage-backend-security-review-W05-P12-S26]]'
  - '[[2026-06-14-storage-backend-security-review-adr]]'
  - '[[2026-06-14-storage-backend-security-review-plan]]'
  - '[[2026-06-14-storage-backend-security-review-research]]'
---

# `storage-backend-security-review` feature index

Auto-generated index of all documents tagged with `#storage-backend-security-review`.

## Documents

### adr

- `2026-06-14-storage-backend-security-review-adr` - `storage-backend-security-review` adr: `close the residual secure-storage security, enrollment, and standardisation gap` | (**status:** `accepted`)

### exec

- `2026-06-14-storage-backend-security-review-W01-P02-S03` - Accept an in-memory binary stream in the bbox declaration parse path so no decrypted bytes touch disk
- `2026-06-14-storage-backend-security-review-W01-P02-S04` - Delete the temporary sensitive PDF helper and fold the bbox branch into the in-memory bytes path
- `2026-06-14-storage-backend-security-review-W01-P03-S05` - Apply the manifest KDF validation window to the file-fallback parameters on read and reject below-floor Argon2 cost
- `2026-06-14-storage-backend-security-review-W01-P03-S06` - Delete the dead non-atomic _write_bytes_secure method and its sensitive-persistence-policy allowlist entries
- `2026-06-14-storage-backend-security-review-W03-P05-S10` - Set SQLite busy_timeout in the bucket engine connect listener so a concurrent invocation waits rather than failing immediately with database-locked
- `2026-06-14-storage-backend-security-review-W03-P05-S11` - Add a concurrent-writer regression proving two sessions on one bucket do not raise an immediate database-locked error
- `2026-06-14-storage-backend-security-review-W03-P06-S12` - fsync the staged tmp file and the parent directory before and after os.replace on the manifest write
- `2026-06-14-storage-backend-security-review-W03-P06-S13` - Re-read and re-validate the holder PID immediately before the stale-lock reclaim unlink
- `2026-06-14-storage-backend-security-review-W04-P07-S15` - Replace the resolved absolute source_path provenance with a relative filename or sha-only reference in the raw transaction model
- `2026-06-14-storage-backend-security-review-W04-P07-S16` - Add a cross-OS transaction provenance roundtrip test proving rehydration does not mutate the persisted shape
- `2026-06-14-storage-backend-security-review-W04-P09-S19` - Compare the manifest label against the record display_name in verify_profile_integrity and raise on divergence
- `2026-06-14-storage-backend-security-review-W05-P11-S24` - Rebind the private bucket-submodule imports in profile health and overview to the bucket package surface
- `2026-06-14-storage-backend-security-review-W05-P12-S26` - Replace the three private secure-objects-for-bucket route helpers with the canonical secure_object_repository_for_bucket wrapper

### plan

- `2026-06-14-storage-backend-security-review-plan` - `storage-backend-security-review` plan

### research

- `2026-06-14-storage-backend-security-review-research` - `storage-backend-security-review` research: `secure storage backend adversarial and structural audit`
