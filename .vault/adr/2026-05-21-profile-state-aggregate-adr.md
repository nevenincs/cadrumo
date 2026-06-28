---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-20-cli-state-architecture-research]]"
  - "[[2026-05-21-profile-uuid-identity-adr]]"
  - "[[2026-05-21-state-read-projection-adr]]"
  - "[[2026-05-21-cli-testimonial-reference]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` adr: `Profile state is one aggregate, owned by one repository, written through a cross-store unit-of-work` | (**status:** `accepted`)

## Problem Statement

A logical profile is not one record. It is, concretely, all of: a
bucket directory on disk, a manifest file, an encrypted row in a
per-bucket secure-objects SQLite table, a plaintext active-profile
pointer file, a manifest-scan computed view, and - for auth -
lock/token files under a separately-rooted `.tokens/` directory.

No object owns the profile across those stores. Every operation
writes the stores it happens to know about, and consistency is by
convention. The testimonial cluster
(`[[2026-05-20-cli-state-architecture-research]]`) proves the cost:

- `rename` mutated the SQLite record, moved the directory, rewrote the
  manifest and pointer - with no transaction across them. A failure
  mid-sequence left a ghost profile (registry ahead of filesystem) or
  a `missing_profile_record` (record keyed to the old location).
- `overview` could not see work units `calculate` wrote, because the
  two surfaces touch different store subsets.
- `auth test` returned an empty profile while `auth status` did not.

The UUID-identity ADR (`[[2026-05-21-profile-uuid-identity-adr]]`)
removes the *identity-coupled-to-location* root cause. This ADR
removes the second root cause: **no aggregate owns the entity, and no
transaction boundary spans its stores.**

## Considerations

- **Aggregate per logical entity.** A `Profile` is one aggregate -
  one in-memory object holding identity, label, manifest data, the
  secure record, and lifecycle state. The aggregate, not a loose set
  of stores, is what application code manipulates.
- **One repository, sole writer.** A single `ProfileRepository`
  load/save/create/delete is the *only* code that writes a profile's
  physical stores. No CLI handler and no application service writes a
  store directly. This is what makes "touch every store" structural
  rather than remembered.
- **Cross-store unit-of-work.** With UUID identity, `rename` is
  metadata-only and needs no cross-store atomicity. The remaining
  multi-store mutations are `create` and `delete`. Each must be
  atomic or carry a tested rollback: stage the filesystem directory +
  manifest first (a directory with no secure-object row is
  detectable, reclaimable garbage), commit the SQLite row in a
  transaction, update the pointer last. A failure rolls back the
  staged directory or leaves it as garbage the `repair` surface
  reclaims - never a half-live profile.
- **Read-time integrity validation.** `assess_active_profile_health`
  already validates one profile's stores agree. Generalise it: every
  `ProfileRepository.load` runs an integrity check and surfaces drift
  instead of silently serving an inconsistent profile.
- **Event model - log, not source.** The bucket-event-history system
  is an append-only audit trail written *alongside* state. This ADR
  keeps it that way and explicitly rejects event-sourcing: rebuilding
  all profile/workspace state as an event projection is a far larger
  rewrite, and the aggregate + repository + unit-of-work already give
  write-side consistency by construction. Integrity is enforced by
  the repository and the read-time validator, not by replaying
  events. Event-sourcing may be reconsidered in a future ADR if the
  audit log ever needs to become authoritative.
- **One state root.** `AEAT_LOCAL_STORAGE_ROOT` must root *every*
  profile store, including the token/lock directory. Today the token
  dir sits at repo-root `.tokens/`, outside the root - so the
  isolation contract that tests and the persona harness rely on is
  silently false.

## Constraints

- `ProfileRepository` is the only code that writes a profile's
  physical stores. Direct store writes from CLI handlers or
  application services are forbidden.
- Every multi-store mutation (`create`, `delete`) is atomic or
  carries a tested rollback. A partial-write state must be either
  impossible or detectable-and-reclaimable - never a silently
  half-live profile.
- `ProfileRepository.load` runs a cross-store integrity check and
  surfaces drift; it never silently serves an inconsistent aggregate.
- Every profile store, token and lock files included, is rooted under
  `AEAT_LOCAL_STORAGE_ROOT`.
- Bucket events remain append-only audit records; they are not the
  source of state.
- Per the apex CLI ADR, the CLI root surface stays `config` / `app`;
  this ADR authorises no new root verbs.

## Implementation

### 1. The aggregate

- `ProfileAggregate` - a typed model holding `profile_id` (UUID),
  `label`, manifest fields, the secure profile record, and the
  lifecycle state. It is the unit application code loads and saves.

### 2. The repository

- `ProfileRepository` with `create(label) -> ProfileAggregate`,
  `load(profile_id) -> ProfileAggregate`, `save(aggregate)`,
  `delete(profile_id)`, `list() -> Sequence[ProfileSummary]`.
- `save` and `create` perform the cross-store write as a unit-of-work
  (staged filesystem, transactional SQLite commit, pointer last).
- `delete` tombstones via the lifecycle state, not a destructive
  removal.
- Every CLI profile verb and every application service routes through
  this repository; the name-as-id call-site sweep (tracked in the
  shared plan) repoints all 22 sites at it.

### 3. Integrity validation

- `verify_profile_integrity(aggregate)` - generalises
  `assess_active_profile_health`: checks the manifest, the
  secure-object row, the pointer, and the directory all agree on
  `profile_id`. Run on every `load`.

### 4. One state root

- Relocate the token/lock directory under `AEAT_LOCAL_STORAGE_ROOT`.
  Auth token/lock filenames are keyed by UUID per the UUID ADR; this
  ADR adds the requirement that they live inside the storage root.

## Rationale

An aggregate with a single owning repository converts "every
mutation must remember to touch every store" from a discipline into a
structural guarantee - there is exactly one place that writes, and it
writes all stores or none. Combined with UUID identity (which makes
`rename` metadata-only and shrinks the cross-store surface to
`create`/`delete`), the partial-write defect class is closed by
construction. Keeping events as an audit log avoids a disproportionate
event-sourcing rewrite while the aggregate already delivers write
consistency. Rooting every store under one path makes the isolation
contract true.

## Consequences

- The partial-write defect class (ghost profiles,
  `missing_profile_record`) is eliminated structurally.
- All 22 name-as-id call sites are repointed at the repository; this
  is real blast radius, tracked in the shared plan.
- `repair` gains a defined role: reclaim detectable garbage
  directories left by a rolled-back `create`.
- Event-sourcing is explicitly deferred; if the audit log must later
  become authoritative, that is a new ADR.
- The token/lock directory moves; any state outside the new root is
  abandoned per the clean-cutover decision in the UUID ADR.
