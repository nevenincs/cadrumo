---
tags:
  - "#adr"
  - "#profile-portability"
date: '2026-08-13'
related:
  - "[[2026-08-13-profile-password-custody-research]]"
supersedes:
  - '2026-05-27-profile-portability-adr'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:2aa0f84747fe0e25f4fd80bfd71ee633fc034ba4b060f765bce121af4e7e9435'
---
# `profile-portability` adr: `structured profile portability boundary` | (**status:** `accepted`)

## Problem Statement

User-reviewed structured transfer remains useful but must not masquerade as restorative backup or preserve custody identity.

## Considerations

- Restorative archives preserve UUID, DEK, and custody under `2026-08-13-profile-password-custody-rollup-adr`.
- Portable transfer represents selected logical data, not encrypted storage internals.

## Considered options

- Reuse the restorative archive: rejected because transfer and recovery have different identity semantics.
- Keep a separate structured export/import: accepted.

## Constraints

Portable imports target a newly enrolled profile with a new UUID, password envelope, DEK, and `dek_epoch`. No legacy custody is adopted.

## Implementation

The portability owner defines a versioned, reviewable logical-data bundle with provenance, completeness declarations, collision policy, and explicit import selection. Export excludes password envelopes, DEKs, recovery records, sessions, keyring state, and storage implementation artifacts. Import validates the bundle, presents intended changes, and writes only through current profile application owners after new-profile enrollment.

## Rationale

Logical portability remains understandable and host-independent without becoming a second backup or custody format.

## Consequences

Transfer cannot restore the original cryptographic identity or serve as disaster recovery.
