---
tags:
  - "#adr"
  - "#sealed-archive-transport"
date: '2026-08-13'
related:
  - '[[2026-08-13-profile-password-custody-research]]'
  - '[[2026-08-13-profile-password-custody-rollup-adr]]'
supersedes:
  - '2026-06-03-bucket-sealed-archive-adr'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:32437c2f03ba7265415de3cdd7085336273c28e68599b5e75c17bc2d8cf781dd'
---
# `sealed-archive-transport` adr: `sealed archive transport boundary` | (**status:** `accepted`)

## Problem Statement

Archive framing and hostile-input handling remain distinct from the custody content root and restore authorization.

## Considerations

- Restorative custody contents and restore modes belong to `2026-08-13-profile-password-custody-rollup-adr`.
- Transport must be deterministic and safe before decryption.

## Considered options

- Let archive transport define custody members: rejected because recovery coupling reappears.
- Keep transport mechanics independent: accepted.

## Constraints

Transport parsing is bounded, duplicate-free, traversal-safe, and no-follow. It may not autodiscover recovery artifacts.

## Implementation

The archive adapter owns canonical header encoding, deterministic member order and metadata, streaming digests, size and count ceilings, duplicate refusal, path normalization, and staging cleanup. It yields validated current-format members to the restore application service. The custody roll-up exclusively defines the mandatory content root, password-only restore, the explicit `restore --artifact` recovery-proof door within the single restore grammar, collision refusal, and capsule publication.

## Rationale

Transport safety can remain stable while custody formats change through explicit successor decisions.

## Consequences

Optional recovery never changes archive completeness. Transport code cannot choose an unlock mechanism.

