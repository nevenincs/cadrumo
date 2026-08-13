---
tags:
  - "#adr"
  - "#profile-disaster-operations"
date: '2026-08-13'
related:
  - "[[2026-08-13-profile-password-custody-research]]"
supersedes:
  - '2026-05-19-profile-lifecycle-disaster-adr'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:6e55d6c7b8731c21f670db4b5be2ab139b9e582b1f39824bbfd58d4ecfbda2dd'
---
# `profile-disaster-operations` adr: `profile disaster operation boundaries` | (**status:** `accepted`)

## Problem Statement

Operators need truthful local incident and disaster actions without silently expanding them into remote or AEAT mutations.

## Considerations

- Custody restore and local deletion belong to `2026-08-13-profile-password-custody-adr`.
- External effects require separate authorization and evidence.

## Considered options

- One cleanup command spanning local and remote owners: rejected because consent and failure domains differ.
- Separate explicit owner operations: accepted.

## Constraints

Every destructive operation performs legal and filing-hold preflight, exact-target confirmation, crash-resumable journaling where applicable, and a durable receipt.

## Implementation

Disaster diagnostics report local capsule state, available operator-owned backups, retained recovery exports, and known remote registrations without exposing secrets. Local reset, restore, and delete delegate to the custody roll-up. Certificate revocation, remote token revocation, cloud deletion, AEAT interaction, and backup destruction each require their own command, authentication, confirmation, journal, and owner receipt. A local operation reports retained external state and never treats it as completed.

## Rationale

Separate authority preserves consent and makes partial disaster handling auditable.

## Consequences

Operators may need several explicit operations, but no local cleanup silently changes an external system.
