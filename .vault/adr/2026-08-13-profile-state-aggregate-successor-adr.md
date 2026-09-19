---
tags:
  - "#adr"
  - "#profile-state-aggregate"
date: '2026-08-13'
related:
  - "[[2026-08-13-profile-password-custody-research]]"
supersedes:
  - '2026-05-21-profile-state-aggregate-adr'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:485d2aa22fa2a06a21e2a6382f1a5e608b0e85dc140348f207d5e339b1e7a4da'
---
# `profile-state-aggregate` adr: `non-authoritative profile state projection` | (**status:** `accepted`)

## Problem Statement

Profile views need a coherent aggregate without turning copied custody fields into authority. The profile also needs one canonical encrypted owner for typed `UserProfileRecord` facts after the retired mixed lifecycle repository is removed.

## Considerations

- Password custody, capsule publication, and physical deletion are owned by `2026-08-13-profile-password-custody-rollup-adr`.
- The profile-password custody research establishes that sensitive profile facts must remain encrypted under the owning profile's independent key boundary.
- Projection drift must not block valid password login or become permission to mutate profile facts.

## Considered options

- Preserve one mixed repository for discovery, custody, labels, facts, and lifecycle mutation: rejected because it retains the superseded authority and creates competing writers.
- Store typed facts in the commit marker or plaintext label projection: rejected because those surfaces are non-secret discovery and publication records.
- Keep an encrypted semantic fact owner inside committed capsule data and compose a separate read model from canonical owners: accepted.

## Constraints

The aggregate contains no password KDF, wrapped DEK, recovery wrap, session key, backend selector, or writable copy of canonical facts. Discovery, listing, UUID resolution, label resolution, and selection do not unlock profile data. No repository constructs a provider or master key, and no retired record format or compatibility parser remains.

## Implementation

`ProfileLifecycleService` is the sole physical lifecycle writer. A separately named `ProfileRecordRepository` is the sole semantic persistence owner for the current `UserProfileRecord`; it has no create-capsule, restore, select, delete-profile, label, manifest, or recovery authority. The record is one strict encrypted row in the profile-local secure-object database carried by the committed capsule's `data/` inventory and encrypted under that capsule's DEK.

Every fact read and mutation requires an authenticated profile session bound to the same immutable UUID, current committed capsule, DEK epoch, and current password-envelope generation and digest. The record retains its schema identity, immutable profile UUID, typed facts, setup state, and canonical UTC creation and update instants. It does not duplicate the presentation label and does not represent physical deletion through a tombstone, removal instant, or reactivation state.

The current record carries a monotonically increasing record revision, the previous-record digest except at revision one, and a canonical content digest. Reads accept only the exact current schema. Mutations compare the expected revision and digest, validate UUID and schema, increment the revision, and atomically commit the new encrypted record with its bucket event in the profile-local database. A stale compare refuses. Public generic `save`, prepared-write, and delete-row escape hatches are not part of the application contract; fact changes, setup completion, and any owner-specific bulk refresh use explicit command operations over this compare-and-swap boundary. Immutable filing-time profile snapshots remain a distinct snapshot authority.

The profile aggregate is a read-only composition. Its locked form projects committed UUID, collision-safe label, current-format presence, and explicit provenance while reporting encrypted status and data summary as typed unavailable values. Its unlocked form may project non-secret status or summary derived from the current record and must carry that record's revision and digest provenance. It never embeds a writable `UserProfileRecord` or authorizes an action from copied state. Custody generation or recovery enrollment is displayed only when explicitly obtained from its owning authority. Projection repair follows committed authority and remains idempotent.

## Rationale

Separating physical lifecycle, encrypted semantic state, and presentation projection gives each fact one owner while preserving the per-profile cryptographic boundary selected by the custody ADR. An authenticated, revision-bound record repository supports existing typed fact consumers without allowing their read model to become a second lifecycle or custody authority.

## Consequences

Locked listing remains available without decrypting profile facts, while fact-dependent commands require an authenticated profile session. Callers must handle typed unavailable projections and stale-write refusal. The retired mixed lifecycle repository, generic mutation doors, duplicated display name, tombstone, and reactivation semantics cannot remain as compatibility surfaces.
