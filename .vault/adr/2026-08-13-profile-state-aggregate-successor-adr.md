---
tags:
  - "#adr"
  - "#profile-state-aggregate"
date: '2026-08-13'
related:
  - "[[2026-08-13-profile-password-custody-research]]"
supersedes:
  - '2026-05-21-profile-state-aggregate-adr'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:44600df22827a50e464d7536b08cbcfb649b78e0f64e08a8e1264518f2bd7047'
---
# `profile-state-aggregate` adr: `non-authoritative profile state projection` | (**status:** `accepted`)

## Problem Statement

Profile views need a coherent aggregate without turning copied custody fields into authority.

## Considerations

- The password envelope and independent recovery record are authoritative only in their owners.
- Projection drift must not block valid password login.

## Considered options

- Mirror custody facts into the aggregate as gates: rejected.
- Project non-secret status with provenance: accepted.

## Constraints

The aggregate contains no password KDF, wrapped DEK, recovery wrap, session key, or backend selector.

## Implementation

The profile aggregate projects immutable UUID, label, current-format presence, local data summary, and typed non-secret lifecycle status from canonical owners. Every projected value carries provenance or a typed unavailable state. Custody generation or recovery enrollment may be displayed only when explicitly obtained from the relevant owner; copied manifest values never select keys or authorize actions. Projection repair follows committed authority and remains idempotent.

## Rationale

A read model serves UI and CLI needs without becoming a second semantic home.

## Consequences

Some views may report unavailable status instead of guessing. Valid password custody remains independent of stale projections.
