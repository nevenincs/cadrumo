---
tags:
  - "#adr"
  - "#sealed-archive-transport"
date: '2026-08-13'
related:
  - "[[2026-08-13-profile-password-custody-research]]"
supersedes:
  - '2026-06-03-bucket-sealed-archive-adr'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:a57faf7ce7008691ef47f193c16a880d071e82f38ba939676ee50f717d88acc9'
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

The archive adapter owns canonical header encoding, deterministic member order and metadata, streaming digests, size and count ceilings, duplicate refusal, path normalization, and staging cleanup. It yields validated current-format members to the restore application service. The custody roll-up exclusively defines the mandatory content root, password-only restore, explicit restore-recover grammar, collision refusal, and capsule publication.

## Rationale

Transport safety can remain stable while custody formats change through explicit successor decisions.

## Consequences

Optional recovery never changes archive completeness. Transport code cannot choose an unlock mechanism.

2026-08-18 amendment (campaign-close proof, S24): the canonical verb is `restore --artifact`, not `restore-recover`; the composite spelling was retired before shipping.
