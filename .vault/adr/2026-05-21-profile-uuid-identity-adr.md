---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-21-profile-state-aggregate-adr]]"
  - "[[2026-05-21-state-read-projection-adr]]"
  - "[[2026-05-20-cli-state-architecture-research]]"
  - "[[2026-05-21-cli-testimonial-reference]]"
---

# `cli-workflow-redesign` adr: `Profile identity is a generated UUID; the display name is a decoupled mutable label` | (**status:** `accepted`)

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
- **No dual-key read path.** New code reads only UUID keys. There is
  no fallback to the legacy `user-profile:{name}:{name}` key.
- **Clean cutover, no migration.** Existing on-disk profile state is
  pre-1.0 local development data with no production value. It is
  abandoned, not migrated: no migration command, no compatibility
  window, no rekeying of legacy rows. The objective is an industry-
  grade profile backend built correct from the start, not a bridge
  from a flawed one. Operators recreate profiles on the new backend.

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
- No migration is written and no legacy data is preserved; existing
  secure-storage profile records are abandoned at cutover.
- No backward-compatible dual-key read path is introduced.
- Per the apex CLI ADR, the CLI root surface stays `config` / `app`;
  this ADR authorises no new root verbs.

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

### 4. Cutover - no migration

Existing on-disk profile state is abandoned. No migration command is
written; no legacy `user-profile:{name}:{name}` row is read or
rekeyed; no compatibility window exists. The UUID-identity backend is
the only code path. Any pre-existing local bucket directory is inert
and may be deleted by the operator. New profiles are created directly
on the UUID backend.

This is deliberate: the objective is a verified, tested, industry-
grade profile management backend, and a clean build is both simpler
and more trustworthy than a bridge from the flawed name-as-id design.

### 5. Sequencing

This ADR is the decision. The evolving plan executes it in three
waves: (W1) UUID identity model - `profile_id`, `label`, keys, paths,
manifest, pointer; (W2) `rename` collapse and the name-as-id
call-site sweep, with the legacy code paths deleted; (W3) auth
token/lock filenames keyed by UUID and one-state-root verification.
Every wave lands real-behavior roundtrip and anti-tautology tests
with it. A child ADR is required only if name-uniqueness policy needs
its own adjudication.

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
- Existing local profile state is abandoned at cutover. There is no
  migration and no compatibility window; operators recreate profiles
  on the new backend. Pre-1.0 local-first state makes this acceptable
  and is an explicit, accepted decision.
- Every name-as-id call site (22, per the reference) changes; the
  blast radius is real and is the subject of the plan.
- Bucket directories become opaque UUIDs - operator-facing tooling
  must always resolve through the manifest `label`, never the
  directory name. This is a permanent discipline the plan encodes in
  tests.
- The backend is rebuilt to an industry-grade standard: UUID
  identity, decoupled label, single-key secure objects, and
  roundtrip + anti-tautology test coverage at every persistence
  boundary.
