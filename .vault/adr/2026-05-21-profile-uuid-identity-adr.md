---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-21'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-20-cli-state-architecture-research]]"
  - "[[2026-05-21-cli-testimonial-reference]]"
  - "[[2026-05-16-profile-lifecycle-cli-adr]]"
---

# `cli-workflow-redesign` adr: `Profile identity is a generated UUID; the display name is a decoupled mutable label` | (**status:** `proposed`)

## Problem Statement

A profile's stable identity is currently its human-chosen name. The
name is simultaneously the `bucket_id`, the bucket directory name, the
keystore directory name, the active-profile pointer value, the
manifest `bucket_id`, the auth token/lock filename prefix, and - the
smoking gun - it is doubled into the secure-object key
`user-profile:{bucket_id}:{profile_id}` (today always `{name}:{name}`).

Because identity is the name, and the name is the physical location,
the same logical record is addressed differently depending on where
its directory sits. Consequences verified by testimonial-driven
review (`[[2026-05-20-cli-state-architecture-research]]`):

- `profile rename` cannot be a metadata change. It must move the
  bucket directory, the keystore directory, re-key every SQLite row,
  rewrite the manifest and pointer, and rename token files - across
  SQLite + filesystem with no transaction boundary. The original
  implementation left ghost profiles; the patched implementation left
  a `missing_profile_record` corruption (record keyed to the old
  location) until a further fix re-keyed the row by hand.
- Any name the user might reasonably want (accents, spaces, a renamed
  business) becomes a filesystem path and a DB key.
- The discovery reference catalogues **22 name-as-id call sites across
  12 files**.

A name is operator-facing data; it is mutable by nature. Using it as
the stable identity is the root cause. Every mature system separates a
generated, immutable identity from a mutable display label.

## Considerations

- **UUID vs other stable id.** A UUIDv4 is location-independent,
  collision-free without coordination, and carries no operator
  meaning - exactly the properties a stable id needs. A monotonic
  integer would require a counter store; a content hash would change
  with content. UUIDv4 is the standard choice.
- **Name resolution UX.** Operators must keep typing names, not
  UUIDs. The CLI resolves `name -> profile_id` through the
  manifest-scan view at command entry. This requires display names to
  be unambiguous among *live* profiles.
- **Key de-doubling.** The key `user-profile:{bucket_id}:{profile_id}`
  has always had `bucket_id == profile_id`; the second segment is
  pure redundancy. Under UUID identity there is exactly one
  profile-value record per profile. The key collapses to
  `user-profile:{uuid}`. The snapshot key keeps its discriminator:
  `user-profile-snapshot:{uuid}:{snapshot_id}`.
- **No dual-key read path.** A process cannot serve both
  `user-profile:{name}:{name}` and `user-profile:{uuid}` rows without
  a fragile fallback. The migration must be a one-time forward
  migration; new code reads only UUID keys.
- **Migration atomicity gap.** SQLite row re-keying is transactional;
  the filesystem directory rename is not. A crash between them leaves
  a *detectable* degraded state (UUID keys inside a name-named
  directory) that a re-run repairs. This is acceptable and bounded.

## Constraints

- The generated `profile_id` is a UUIDv4, assigned once at profile
  creation, and is **immutable for the life of the profile**.
- The `display_name` (a.k.a. `label`) is a separate field. It MUST
  NOT appear in any key, path, directory name, pointer value, or
  token filename.
- Display names MUST be unique among live (non-tombstoned) profiles,
  compared case-insensitively, so `name -> uuid` resolution is
  deterministic. A tombstoned profile's name is free to reuse.
- `rename` MUST be a label-only field update: no directory move, no
  re-key, no cross-store transaction.
- The migration MUST run before any UUID-key-consuming code path is
  reachable; a single forward migration, idempotent and re-runnable.
- No backward-compatible dual-key read path is introduced.
- Per the apex CLI ADR, the CLI root surface stays `config` / `app`;
  the only new verb this ADR authorises is the one-time migration
  command.

## Implementation

### 1. Identity model

- `UserProfileRecord` / the bucket manifest gain a `profile_id`
  (UUIDv4 string) as the stable id and a `label` (display name) as a
  mutable field. The manifest persists both: `profile_id` (uuid) and
  `label` (name).
- The `bucket_id == profile_id` convention in
  `application/user_profile/_orchestration.py` (lines 9-12, 171, 314,
  347) is broken: `bucket_id` becomes the UUID; the name is never an
  id again.

### 2. Keys and paths

- `user_profile_value_object_key` -> `f"user-profile:{uuid}"`
  (`_repository.py`).
- `user_profile_snapshot_object_key` ->
  `f"user-profile-snapshot:{uuid}:{snapshot_id}"`.
- The bucket directory (`_layout.py` `bucket_paths`) and the keystore
  directory (`_keystore_paths.py`) are named by the UUID.
- `BucketManifest.bucket_id` carries the UUID; a `label` field carries
  the name.
- `BucketPointer` stores the UUID.
- `_profile_bucket_scan.py` reads the display name from the manifest
  `label`, not from the directory name (the directory name is now an
  opaque UUID).
- Auth token/lock filenames (5 sites under `auth/` and `browser/`)
  use the UUID prefix.

### 3. `rename`

`LifecycleService.rename` and the CLI `config profile rename` handler
collapse to: load the profile record, set `label`, save. No
`shutil.move`, no engine disposal, no re-key, no rollback machinery.
The current rename handler's directory-move/re-key block is deleted.

### 4. Migration

A one-time, idempotent `aeat config migrate-profile-uuid` command
(the only new verb). Sequence, per the discovery reference's
migration considerations:

1. Inventory every bucket directory; read each manifest for the
   display name; generate a UUIDv4 per bucket; write a durable
   `name -> uuid` mapping before any mutation.
2. Re-key the secure-object rows in a single SQLite transaction
   (reversible).
3. Rewrite the manifest: `bucket_id` = uuid, `label` = name.
4. Rename the bucket and keystore directories to the UUID (the
   non-transactional step).
5. Rewrite the active-profile pointer to the UUID.
6. Rename token files best-effort; delete lock files (TTL expiry
   already handles staleness). A missing token file forces
   re-authentication - not data loss.

Crash recovery: a degraded state (UUID keys in a name-named
directory) is detectable by comparing the manifest `bucket_id` to the
directory name; the command re-run repairs it.

### 5. Sequencing

This ADR is the decision. A follow-up evolving plan executes it in
waves: (W1) identity model + keys + paths behind the migration;
(W2) the migration command; (W3) `rename` collapse and the
name-as-id call-site sweep; (W4) auth token/lock filenames. Each wave
is a Codex-assisted refactor with tracked audits. A child ADR is
required only if name-uniqueness policy or the migration-command UX
needs its own adjudication.

## Rationale

Separating a generated immutable identity from a mutable label is the
standard, correct shape and the minimal change that dissolves an
entire defect class: with the name no longer an id, `rename` cannot
corrupt state because there is nothing to move or re-key. It also
frees the display name to be anything the operator wants. The
de-doubled UUID key is simpler than today's redundant key. The
one-time forward migration is bounded, idempotent, and crash-safe by
construction.

## Consequences

- The `profile rename` corruption class is eliminated by design, not
  patched.
- A single, breaking, one-time migration is required; there is no
  dual-key compatibility window. Pre-1.0 local-first state makes this
  acceptable.
- Every name-as-id call site (22, per the reference) changes; the
  blast radius is real and is the subject of the follow-up plan.
- Bucket directories become opaque UUIDs - operator-facing tooling
  must always resolve through the manifest `label`, never the
  directory name. This is a permanent discipline the plan must encode
  in tests.
- Auth re-authentication may be required once after migration if
  token-file rename is skipped; this is a one-time, recoverable cost.
