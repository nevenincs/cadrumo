---
tags:
  - "#adr"
  - "#profile-bucket-lifecycle"
date: '2026-08-13'
related:
  - "[[2026-08-13-profile-password-custody-research]]"
supersedes:
  - '2026-05-14-profile-bucket-lifecycle-adr'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:eecc6f07b474c262cb6599b470d9a021fe62dcd743a069a47dfb2e992d17efd1'
---
# `profile-bucket-lifecycle` adr: `current-format profile capsule lifecycle` | (**status:** `accepted`)

## Problem Statement

Profile naming, discovery, selection, and local data ownership remain necessary after custody moves to the profile-password roll-up. This successor preserves only those independent lifecycle facts.

## Considerations

- Custody and atomic capsule publication belong to `2026-08-13-profile-password-custody-adr`.
- A display label is mutable presentation; the immutable UUID is identity.
- Discovery must not infer profiles from arbitrary directories.

## Considered options

- Preserve the mixed lifecycle-and-custody ADR: rejected because it leaves two authorities.
- Retain only non-custody lifecycle facts here: accepted.

## Constraints

The profile repository remains the canonical owner of label-to-UUID resolution and selected-profile projection. It may not unwrap keys or infer retired formats.

## Implementation

Profiles are addressed internally by immutable UUID. Labels remain mutable, non-secret presentation with collision-safe validation. Listing and selection project only committed current-format capsules. Profile-scoped application services resolve UUID before opening data. Capsule publication, password custody, pointer compare-and-swap, restore, and local deletion delegate exclusively to `2026-08-13-profile-password-custody-adr`.

## Rationale

Separating identity and discovery from cryptographic custody preserves useful lifecycle ownership without restating the superseded provider design.

## Consequences

The repository can evolve labels and projections independently. It cannot introduce another activation, key, restore, or deletion protocol.
