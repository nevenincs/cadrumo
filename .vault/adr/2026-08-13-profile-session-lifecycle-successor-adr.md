---
tags:
  - "#adr"
  - "#profile-session-lifecycle"
date: '2026-08-13'
related:
  - "[[2026-08-13-profile-password-custody-research]]"
  - '[[2026-08-13-profile-password-custody-rollup-adr]]'
supersedes:
  - '2026-07-24-profile-login-session-adr'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:abfdc5fa64ab60145e483fadb133dec2c243c1866653c4e13ca3ad052509e5d8'
---
# `profile-session-lifecycle` adr: `authenticated profile session lifecycle` | (**status:** `accepted`)

## Problem Statement

The application still needs one explicit active-profile session lifecycle after session-key custody moves to the roll-up.

## Considerations

- Cryptographic session creation, deadlines, handover ordering, and keyring acceleration belong to `2026-08-13-profile-password-custody-rollup-adr`.
- UI and command surfaces must project application session truth.

## Considered options

- Let each entrypoint own session state: rejected because state and cleanup diverge.
- Keep one application lifecycle owner: accepted.

## Constraints

Presentation cannot synthesize authentication, revive a retired session, or convert a keyring failure into profile failure.

## Implementation

One application service owns active-session observation, explicit close, inactivity events, process shutdown cleanup, and operator-safe status projection. Entrypoints request transitions and render typed outcomes. They do not manipulate keys or session files. Failed candidate authentication leaves the current application session unchanged; the custody roll-up defines the underlying atomic handover.

## Rationale

One lifecycle owner gives every CLI and TUI surface the same active-profile truth without duplicating custody.

## Consequences

Operator surfaces remain consistent. The service depends on, but does not restate, the custody session contract.
