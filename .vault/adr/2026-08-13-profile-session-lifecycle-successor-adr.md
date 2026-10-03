---
tags:
  - "#adr"
  - "#profile-session-lifecycle"
date: '2026-08-13'
related:
  - "[[2026-08-13-profile-password-custody-research]]"
  - '[[2026-08-13-profile-password-custody-rollup-adr]]'
  - '[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]'
  - '[[2026-09-26-mcp-purpose-authentication-adr]]'
supersedes:
  - '2026-07-24-profile-login-session-adr'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:0e5818c6c62e8eb86634a5faa53bdf76a138092f92d745ecb7bb7397d997aa6f'
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

## Amendment 2026-09-26: separate caller sessions under one lifecycle owner

Accepted under the operator's instruction to continue the presented mcp-purpose-authentication plan. The single application lifecycle owner now manages separately identified human, attended and API-authenticated sessions, as governed by 2026-09-26-mcp-purpose-authentication-profile-access-adr and hosted under 2026-09-26-mcp-purpose-authentication-adr.

Active profile means the selected target of one human frontend context, never ambient authorization for every agent. Candidate handover preserves that context on failure and does not redirect another session. Current-session lock/logout, key/grant revocation and profile-wide suspension are distinct application transitions. Entrypoints render the resulting status and remaining access, without inferring authentication from process presence.

Human acceleration, API grant validity, access leases, operation ownership and durable work retain their separate authorities. This amendment extends lifecycle scope; it does not move key manipulation or policy into CLI, TUI or MCP.
